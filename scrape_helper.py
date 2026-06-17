# scrape_helper.py
import time
import traceback
from PyQt5.QtCore import QThread, QTimer, QCoreApplication, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import QDialog, QMessageBox
from config import CHUNK_SIZE, STALL_TIMEOUT, MAX_CONCURRENT_SCRAPES
from match_dialog import MatchDialog
from metadata_helper import merge_and_apply_metadata
import scraping


class GameScrapeWorker(QObject):
    finished = pyqtSignal(int, dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(int, str)

    def __init__(self, row_index: int, game: dict, parent=None):
        super().__init__(parent)
        self.row_index = row_index
        self.game = game
        self.cancelled = False

    def run(self):
        try:
            title = self.game.get("title") or self.game.get("original_title") or ""
            if not title:
                self.finished.emit(self.row_index, {})
                return
            if self.cancelled:
                self.finished.emit(self.row_index, {})
                return
            meta = scraping.scrape_igdb_then_steam(
                None, title, auto_accept_score=92, fetch_pcgw_save=False
            ) or {}
            if self.cancelled:
                self.finished.emit(self.row_index, {})
                return
            if "__candidates__" in meta:
                result = {"__candidates__": meta["__candidates__"]}
            else:
                result = meta
            self.finished.emit(self.row_index, result)
        except Exception as e:
            print(f"[SCRAPE WORKER] Error scraping row {self.row_index}: {e}")
            traceback.print_exc()
            self.error.emit(self.row_index, str(e))


class ScrapeCoordinator:
    def __init__(self, parent_window):
        self.parent = parent_window
        self._active_workers = []
        self._pending_rows = []
        self._scrape_stats = None
        self._cancel_flag = False
        self._pending_manual_matches = {}
        self._active_match_dialogs = []

    def cancel(self):
        if self._cancel_flag:
            return
        self._cancel_flag = True
        self.parent._cancel_current_scrape = True
        for worker, thread, _ in self._active_workers:
            worker.cancelled = True
            if thread.isRunning():
                thread.quit()
                thread.wait(500)
        self._active_workers.clear()
        self._pending_rows.clear()
        self.parent.progress_bar.setVisible(False)

    def scrape_all(self, auto_accept_score=92):
        games = self.parent.games
        if not games:
            self.parent.status.setText("No titles to scrape.")
            return
        rows_to_process = [
            i for i, g in enumerate(games)
            if not (str(g.get("app_id") or "").strip() or str(g.get("igdb_id") or "").strip())
        ]
        if not rows_to_process:
            self.parent.status.setText("No titles to scrape.")
            QMessageBox.information(self.parent, "Scrape Complete",
                                    "All games already have a valid Steam ID or IGDB ID. Nothing to scrape.")
            return
        self._cancel_flag = False
        self.parent._cancel_current_scrape = False
        self.parent.scrape_btn.setEnabled(False)
        self.parent.cancel_scrape_btn.setVisible(True)
        self._scrape_stats = {
            "total": len(rows_to_process),
            "successful": 0,
            "failed": 0,
            "manual_needed": 0,
            "start_time": time.time()
        }
        self._pending_manual_matches = {}
        self._active_match_dialogs = []
        self._pending_rows = list(rows_to_process)
        self._active_workers = []
        # Show progress bar
        self.parent.progress_bar.setVisible(True)
        self.parent.progress_bar.setMaximum(len(rows_to_process))
        self.parent.progress_bar.setValue(0)
        # Start workers
        for _ in range(min(MAX_CONCURRENT_SCRAPES, len(self._pending_rows))):
            self._start_next_worker()

    def _start_next_worker(self):
        if self._cancel_flag or self.parent._cancel_current_scrape:
            if not self._active_workers:
                self._finish_scraping()
            return
        if not self._pending_rows:
            if not self._active_workers:
                self._finish_scraping()
            return
        row_index = self._pending_rows.pop(0)
        game = self.parent.games[row_index]
        title = game.get("title") or game.get("original_title") or f"Game {row_index}"
        processed = self._scrape_stats["successful"] + self._scrape_stats["failed"] + self._scrape_stats["manual_needed"]
        self.parent.status.setText(f"Scraping: {title} ({processed+1}/{self._scrape_stats['total']})")
        self.parent.progress_bar.setValue(processed)
        worker = GameScrapeWorker(row_index, game)
        thread = QThread(self.parent)
        worker.moveToThread(thread)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        thread.started.connect(worker.run)
        thread.start()
        self._active_workers.append((worker, thread, row_index))

    def _on_worker_finished(self, row_index, result):
        worker_data = None
        for i, (w, t, idx) in enumerate(self._active_workers):
            if idx == row_index:
                worker_data = self._active_workers.pop(i)
                break
        if worker_data:
            w, t, _ = worker_data
            if t.isRunning():
                t.quit()
                t.wait(500)
        if not self._cancel_flag and not self.parent._cancel_current_scrape:
            if "__candidates__" in result:
                self._scrape_stats["manual_needed"] += 1
                self._pending_manual_matches[row_index] = {
                    "game": self.parent.games[row_index] if row_index < len(self.parent.games) else None,
                    "candidates": result["__candidates__"],
                    "processed": False
                }
            elif result:
                try:
                    if row_index < len(self.parent.games):
                        merge_and_apply_metadata(self.parent.games, self.parent.model, row_index, result, self.parent)
                        self._scrape_stats["successful"] += 1
                        self.parent.mark_dirty()
                    else:
                        self._scrape_stats["failed"] += 1
                except Exception as e:
                    print(f"[SCRAPE] Merge error for row {row_index}: {e}")
                    self._scrape_stats["failed"] += 1
            else:
                self._scrape_stats["failed"] += 1
        else:
            self._scrape_stats["failed"] += 1
        self._start_next_worker()

    def _on_worker_error(self, row_index, error_msg):
        print(f"[SCRAPE] Error scraping row {row_index}: {error_msg}")
        self._scrape_stats["failed"] += 1
        self._on_worker_finished(row_index, {})

    def _finish_scraping(self):
        if self._pending_manual_matches and not self._cancel_flag:
            self.parent.status.setText(f"Processing {len(self._pending_manual_matches)} manual matches...")
            self._process_pending_manual_matches()
        else:
            self._show_final_report()
        self.parent.progress_bar.setVisible(False)

    def _process_pending_manual_matches(self):
        if self._cancel_flag:
            self._show_final_report()
            return
        if not self._pending_manual_matches:
            self._show_final_report()
            return
        row_index, match_info = next(iter(self._pending_manual_matches.items()))
        if match_info.get("processed"):
            del self._pending_manual_matches[row_index]
            QTimer.singleShot(0, self._process_pending_manual_matches)
            return
        game = match_info["game"]
        if game is None:
            del self._pending_manual_matches[row_index]
            QTimer.singleShot(0, self._process_pending_manual_matches)
            return
        candidates = match_info["candidates"]
        dlg = MatchDialog({
            "title": game.get("title", ""),
            "original_title": game.get("original_title", ""),
            "description": game.get("description", "")
        }, candidates, parent=self.parent)
        self._active_match_dialogs.append(dlg)
        result = dlg.exec_()
        self._active_match_dialogs.remove(dlg)
        if not self._cancel_flag and result == QDialog.Accepted:
            result_data = dlg.result_dict or {}
            chosen = result_data.get("chosen_candidate") or {}
            chosen_appid = chosen.get("id") or chosen.get("app_id")
            if chosen_appid:
                selected_title = result_data.get('title') or chosen.get('name') or game.get("title", "")
                selected_igdb_id = result_data.get('igdb_id')
                selected_app_id = result_data.get('app_id') or result_data.get('steam_id')
                if selected_igdb_id in ("N/A", ""):
                    selected_igdb_id = None
                if selected_app_id in ("N/A", ""):
                    selected_app_id = None
                try:
                    meta = scraping.scrape_igdb_then_steam(
                        igdb_id=selected_igdb_id,
                        title=selected_title,
                        auto_accept_score=92,
                        fetch_pcgw_save=False,
                        steam_app_id=selected_app_id
                    ) or {}
                    if meta and "__candidates__" not in meta:
                        merge_and_apply_metadata(self.parent.games, self.parent.model, row_index, meta, self.parent)
                        self._scrape_stats["successful"] += 1
                        self.parent.mark_dirty()
                    else:
                        self._scrape_stats["failed"] += 1
                except Exception as e:
                    print(f"[SCRAPE] Manual match error: {e}")
                    self._scrape_stats["failed"] += 1
            else:
                self._scrape_stats["failed"] += 1
        else:
            self._scrape_stats["failed"] += 1
        match_info["processed"] = True
        del self._pending_manual_matches[row_index]
        QTimer.singleShot(0, self._process_pending_manual_matches)

    def _show_final_report(self):
        elapsed = time.time() - self._scrape_stats["start_time"]
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        success_rate = (self._scrape_stats["successful"] / self._scrape_stats["total"] * 100) if self._scrape_stats["total"] > 0 else 0
        report = f"""
        ╔══════════════════════════════════════════════╗
        ║            SCRAPING COMPLETE                ║
        ╚══════════════════════════════════════════════╝

        📊 SUMMARY
        • Total Processed: {self._scrape_stats['total']} games
        • Successful: {self._scrape_stats['successful']}
        • Failed: {self._scrape_stats['failed']}
        • Manual Matches Needed: {self._scrape_stats['manual_needed']}
        • Success Rate: {success_rate:.1f}%
        • Time: {minutes:02d}:{seconds:02d}
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Scraping Results")
        msg_box.setText(report)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec_()
        self.parent.refresh_model()
        self.parent.status.setText(f"Scraping complete: {self._scrape_stats['successful']} successful, {self._scrape_stats['failed']} failed, {self._scrape_stats['manual_needed']} manual")
        self.parent.scrape_btn.setEnabled(True)
        self.parent.cancel_scrape_btn.setVisible(False)