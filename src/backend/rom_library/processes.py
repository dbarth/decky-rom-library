"""The processes of a game Steam runs, and a clean quit for its emulator."""
import os
import signal
import time

# The FUSE helpers of an AppImage, which stop once the app does. uruntime runs its helper from a
# memfd: the kernel names it memfd:…, and its argv[0] holds the helper's name.
HELPERS = {"dwarfs", "squashfuse", "fusermount", "fusermount3"}


def helper(comm, argv):
    return comm in HELPERS or comm.startswith("memfd:") or bool(argv) and os.path.basename(argv[0]) in HELPERS


class Processes:
    """proc, kill, clock and sleep are /proc and the os and time calls, which tests replace."""

    def __init__(self, proc="/proc", kill=os.kill, clock=time.monotonic, sleep=time.sleep):
        self.proc, self.kill, self.clock, self.sleep = proc, kill, clock, sleep

    def table(self):
        """Return {pid: (ppid, comm, state, argv)} for the processes the plugin can read."""
        out = {}
        for name in os.listdir(self.proc):
            if not name.isdigit():
                continue
            try:
                with open(os.path.join(self.proc, name, "stat")) as f:
                    stat = f.read()
                with open(os.path.join(self.proc, name, "cmdline"), "rb") as f:
                    argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
            except OSError:
                continue
            # comm sits in parentheses and may hold spaces: the fields after the last one are fixed.
            comm = stat[stat.index("(") + 1:stat.rindex(")")]
            state, ppid = stat[stat.rindex(")") + 2:].split()[:2]
            out[int(name)] = (int(ppid), comm, state, argv)
        return out

    def reaper(self, table, appid):
        """Return the pid of the reaper Steam starts the game under, else None. Steam's launch
        wrapper lists the same arguments: the reaper is the one whose program is reaper."""
        tag = f"AppId={appid}"
        return next((pid for pid, (_, _, _, argv) in table.items()
                     if argv and os.path.basename(argv[0]) == "reaper" and tag in argv), None)

    def emulator(self, table, root):
        """Return the process that runs the game under root: down the children that are neither FUSE
        helpers nor zombies, to the last one."""
        pid = root
        while True:
            kids = sorted(p for p, (pp, comm, state, argv) in table.items()
                          if pp == pid and not helper(comm, argv) and state != "Z")
            if not kids:
                return pid
            pid = kids[0]

    def descendants(self, table, root):
        out, todo = [], [root]
        while todo:
            parent = todo.pop()
            kids = [p for p, (pp, _, _, _) in table.items() if pp == parent]
            out += kids
            todo += kids
        return out

    def alive(self, pid):
        try:
            with open(os.path.join(self.proc, str(pid), "stat")) as f:
                stat = f.read()
        except OSError:
            return False
        return stat[stat.rindex(")") + 2:].split()[0] != "Z"

    def quit(self, appid, wait=10.0, log=None):
        """Send SIGTERM to the emulator of the game Steam runs under appid, as closing its window
        does, and wait for it to end. After wait seconds, kill what is left of the game. Return
        "quit", "killed", or None when no such game runs. log gets the program that gets SIGTERM."""
        table = self.table()
        reaper = self.reaper(table, appid)
        if reaper is None:
            return None
        target = self.emulator(table, reaper)
        if target == reaper:
            return None
        if log:
            log(f"SIGTERM to {target}: {' '.join(table[target][3][:1])}")
        self.kill(target, signal.SIGTERM)
        end = self.clock() + wait
        while self.clock() < end:
            if not self.alive(target):
                return "quit"
            self.sleep(0.25)
        for pid in self.descendants(self.table(), reaper):
            try:
                self.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return "killed"
