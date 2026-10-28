"""Tests for the game's processes and its clean quit. Run with: python3 -I tests/test_processes.py"""
import os
import shutil
import signal
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from rom_library.processes import Processes  # noqa: E402

APPID = 3492179769
EDEN = "/tmp/.mount_Edenremp7370771859093012500/bin/eden"
# Tunic on the Odin: Steam's launch wrapper, its reaper, the AppImage's runtime, its FUSE mount, Eden
# and a zombie shell of Eden's. ps names the FUSE mount mem…: uruntime runs dwarfs from a memfd.
TREE = [
    (4500, 4192, "steam-launch-wr", "S", ["/home/steamos/.local/share/Steam/linuxarm64/steam-launch-wrapper",
                                          "--", "/home/steamos/.local/share/Steam/steamrtarm64/reaper",
                                          "SteamLaunch", f"AppId={APPID}", "--", "eden"]),
    (36803, 4500, "reaper", "S", ["/home/steamos/.local/share/Steam/steamrtarm64/reaper", "SteamLaunch",
                                  f"AppId={APPID}", "--", "/home/steamos/.local/share/steamos-arm/hub/bin/eden"]),
    (36805, 36803, "Eden.AppImage", "S", ["/home/steamos/Applications/Eden.AppImage", "-f", "-g", "TUNIC.nsp"]),
    (36806, 36805, "memfd:dwarfs", "S", ["dwarfs", "/proc/self/fd/4", "/tmp/.mount_Edenremp7370771859093012500"]),
    (36825, 36805, "eden", "S", [EDEN, "-f", "-g", "TUNIC.nsp"]),
    (36840, 36825, "sh", "Z", []),
]


class ProcessesTest(unittest.TestCase):
    def setUp(self):
        self.proc = tempfile.mkdtemp()
        for pid, ppid, comm, state, argv in TREE:
            self.add(pid, ppid, comm, state, argv)
        self.signals = []
        self.now = 0.0
        self.exits = {}

    def tearDown(self):
        shutil.rmtree(self.proc)

    def add(self, pid, ppid, comm, state, argv):
        folder = os.path.join(self.proc, str(pid))
        os.makedirs(folder)
        with open(os.path.join(folder, "stat"), "w") as f:
            f.write(f"{pid} ({comm}) {state} {ppid} {pid} {pid} 0 -1\n")
        with open(os.path.join(folder, "cmdline"), "wb") as f:
            f.write(b"".join(a.encode() + b"\0" for a in argv))

    def kill(self, pid, sig):
        self.signals.append((pid, sig))
        # A process listed in exits ends that many seconds after SIGTERM.
        if sig == signal.SIGTERM and pid in self.exits:
            self.exits[pid] += self.now

    def sleep(self, seconds):
        self.now += seconds
        for pid, at in list(self.exits.items()):
            if self.signals and at <= self.now:
                shutil.rmtree(os.path.join(self.proc, str(pid)))
                del self.exits[pid]

    def processes(self):
        return Processes(self.proc, kill=self.kill, clock=lambda: self.now, sleep=self.sleep)

    def test_reaper_and_emulator(self):
        p = self.processes()
        table = p.table()
        self.assertEqual(table[36803][1], "reaper")
        self.assertEqual(p.reaper(table, APPID), 36803)
        self.assertEqual(p.emulator(table, 36803), 36825)
        self.assertEqual(sorted(p.descendants(table, 36803)), [36805, 36806, 36825, 36840])

    def test_a_helper_is_known_by_its_program(self):
        shutil.rmtree(os.path.join(self.proc, "36806"))
        self.add(36806, 36805, "3", "S", ["/tmp/.mount_x/dwarfs", "/proc/self/fd/4"])
        p = self.processes()
        self.assertEqual(p.emulator(p.table(), 36803), 36825)

    def test_quit_sends_sigterm_to_the_emulator(self):
        self.exits[36825] = 1.0
        self.assertEqual(self.processes().quit(APPID), "quit")
        self.assertEqual(self.signals, [(36825, signal.SIGTERM)])

    def test_quit_kills_the_game_after_the_wait(self):
        self.assertEqual(self.processes().quit(APPID, wait=10), "killed")
        self.assertEqual(self.signals[0], (36825, signal.SIGTERM))
        self.assertEqual(sorted(pid for pid, sig in self.signals if sig == signal.SIGKILL),
                         [36805, 36806, 36825, 36840])
        self.assertGreaterEqual(self.now, 10)

    def test_quit_without_the_game(self):
        self.assertIsNone(self.processes().quit(1234))
        self.assertEqual(self.signals, [])


if __name__ == "__main__":
    unittest.main()
