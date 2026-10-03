import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from shortcut3ds import banner, tools

UNIQUE_ID_FIRST = 0xF8000
UNIQUE_ID_COUNT = 0x7000
DELIVER_ARG_MAX = 0x300
TARGET_BLOB_MAX = 0x400 - 8

SYSCALLS = {
    "ControlMemory": 1,
    "QueryMemory": 2,
    "ExitProcess": 3,
    "GetProcessAffinityMask": 4,
    "SetProcessAffinityMask": 5,
    "GetProcessIdealProcessor": 6,
    "SetProcessIdealProcessor": 7,
    "CreateThread": 8,
    "ExitThread": 9,
    "SleepThread": 10,
    "GetThreadPriority": 11,
    "SetThreadPriority": 12,
    "GetThreadAffinityMask": 13,
    "SetThreadAffinityMask": 14,
    "GetThreadIdealProcessor": 15,
    "SetThreadIdealProcessor": 16,
    "GetCurrentProcessorNumber": 17,
    "Run": 18,
    "CreateMutex": 19,
    "ReleaseMutex": 20,
    "CreateSemaphore": 21,
    "ReleaseSemaphore": 22,
    "CreateEvent": 23,
    "SignalEvent": 24,
    "ClearEvent": 25,
    "CreateTimer": 26,
    "SetTimer": 27,
    "CancelTimer": 28,
    "ClearTimer": 29,
    "CreateMemoryBlock": 30,
    "MapMemoryBlock": 31,
    "UnmapMemoryBlock": 32,
    "CreateAddressArbiter": 33,
    "ArbitrateAddress": 34,
    "CloseHandle": 35,
    "WaitSynchronization1": 36,
    "WaitSynchronizationN": 37,
    "SignalAndWait": 38,
    "DuplicateHandle": 39,
    "GetSystemTick": 40,
    "GetHandleInfo": 41,
    "GetSystemInfo": 42,
    "GetProcessInfo": 43,
    "GetThreadInfo": 44,
    "ConnectToPort": 45,
    "SendSyncRequest1": 46,
    "SendSyncRequest2": 47,
    "SendSyncRequest3": 48,
    "SendSyncRequest4": 49,
    "SendSyncRequest": 50,
    "OpenProcess": 51,
    "OpenThread": 52,
    "GetProcessId": 53,
    "GetProcessIdOfThread": 54,
    "GetThreadId": 55,
    "GetResourceLimit": 56,
    "GetResourceLimitLimitValues": 57,
    "GetResourceLimitCurrentValues": 58,
    "GetThreadContext": 59,
    "Break": 60,
    "OutputDebugString": 61,
    "ControlPerformanceCounter": 62,
    "CreatePort": 71,
    "CreateSessionToPort": 72,
    "CreateSession": 73,
    "AcceptSession": 74,
    "ReplyAndReceive": 79,
    "InvalidateProcessDataCache": 82,
    "StoreProcessDataCache": 83,
    "FlushProcessDataCache": 84,
}

SERVICES = ["APT:U", "am:u", "fs:USER", "gsp::Gpu", "hid:USER", "ndm:u"]


@dataclass
class Shortcut:
    target: str
    title: str
    publisher: str
    icon: Image.Image
    args: tuple[str, ...] = ()
    deliver: bytes = b""
    unique_id: int | None = None
    id_key: str | None = None

    def resolved_unique_id(self) -> int:
        if self.unique_id is not None:
            return self.unique_id
        key = (self.id_key or "\0".join((self.target, *self.args))).lower().encode() + self.deliver
        return UNIQUE_ID_FIRST + zlib.crc32(key) % UNIQUE_ID_COUNT

    def title_id(self) -> int:
        return 0x0004000000000000 | self.resolved_unique_id() << 8


def target_blob(target: str, args: tuple[str, ...]) -> bytes:
    if not target.startswith("/") or "\0" in target:
        raise ValueError("the target must be an absolute SD path such as /3ds/app/app.3dsx")
    if any(not a or "\0" in a for a in args):
        raise ValueError("an app argument cannot be empty or contain a NUL")
    blob = b"\0".join(s.encode() for s in (target, *args)) + b"\0\0"
    # The stub's argv buffer is 0x400 bytes: a u32 argc, "sdmc:" and the strings.
    if len(blob) > TARGET_BLOB_MAX:
        raise ValueError(f"the target and its arguments are longer than {TARGET_BLOB_MAX} bytes")
    return blob


def rsf(shortcut: Shortcut, romfs: Path) -> str:
    uid = shortcut.resolved_unique_id()
    syscalls = "\n".join(f"    {name}: {num}" for name, num in SYSCALLS.items())
    services = "\n".join(f"   - {s}" for s in SERVICES)
    return f"""BasicInfo:
  Title: "SC{uid:05X}"
  ProductCode: "CTR-H-{uid:05X}"
  Logo: Homebrew
RomFs:
  RootPath: "{romfs}"
TitleInfo:
  Category: Application
  UniqueId: 0x{uid:05X}
Option:
  UseOnSD: true
  FreeProductCode: true
  EnableCrypt: false
  EnableCompress: true
AccessControlInfo:
  CoreVersion: 2
  DescVersion: 2
  ReleaseKernelMajor: "02"
  ReleaseKernelMinor: "33"
  UseExtSaveData: false
  FileSystemAccess:
   - DirectSdmc
  MemoryType: Application
  SystemMode: 64MB
  IdealProcessor: 0
  AffinityMask: 1
  Priority: 16
  MaxCpu: 0x9E
  HandleTableSize: 0x200
  DisableDebug: false
  EnableForceDebug: false
  CanWriteSharedPage: true
  CanUsePrivilegedPriority: false
  CanUseNonAlphabetAndNumber: true
  PermitMainFunctionArgument: true
  CanShareDeviceMemory: true
  RunnableOnSleep: false
  SpecialMemoryArrange: true
  SystemModeExt: Legacy
  CpuSpeed: 268MHz
  EnableL2Cache: false
  CanAccessCore2: false
  MemoryMapping:
   - 1f000000-1f5fffff:r
  SystemCallAccess:
{syscalls}
  ServiceAccessControl:
{services}
SystemControlInfo:
  SaveDataSize: 0K
  RemasterVersion: 0
  StackSize: 0x40000
"""


def build(shortcut: Shortcut, out: Path) -> Path:
    makerom, bannertool = tools.find("makerom"), tools.find("bannertool")
    with tempfile.TemporaryDirectory(prefix="shortcut3ds-") as tmp:
        work = Path(tmp)
        romfs = work / "romfs"
        romfs.mkdir()
        (romfs / "target").write_bytes(target_blob(shortcut.target, shortcut.args))
        if shortcut.deliver:
            if len(shortcut.deliver) > DELIVER_ARG_MAX:
                raise ValueError(f"the deliver arg is longer than {DELIVER_ARG_MAX} bytes")
            (romfs / "deliver").write_bytes(shortcut.deliver)

        icon = shortcut.icon.convert("RGB").resize((48, 48), Image.LANCZOS)
        icon.save(work / "icon.png")
        banner.render(icon, shortcut.title, shortcut.publisher).save(work / "banner.png")
        banner.write_silence(work / "silence.wav")
        (work / "app.rsf").write_text(rsf(shortcut, romfs))

        _run(
            [
                bannertool,
                "makesmdh",
                "-s",
                shortcut.title[:63],
                "-l",
                shortcut.title[:127],
                "-p",
                (shortcut.publisher or "shortcut3ds")[:63],
                "-i",
                work / "icon.png",
                "-o",
                work / "icon.icn",
            ]
        )
        _run(
            [
                bannertool,
                "makebanner",
                "-i",
                work / "banner.png",
                "-a",
                work / "silence.wav",
                "-o",
                work / "banner.bnr",
            ]
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [
                makerom,
                "-f",
                "cia",
                "-o",
                out,
                "-elf",
                tools.stub_elf(),
                "-rsf",
                work / "app.rsf",
                "-icon",
                work / "icon.icn",
                "-banner",
                work / "banner.bnr",
                "-target",
                "t",
                "-ver",
                "0",
            ]
        )
    return out


def _run(cmd: list) -> None:
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise tools.ToolError(f"{Path(str(cmd[0])).name} failed:\n{result.stdout}{result.stderr}")
