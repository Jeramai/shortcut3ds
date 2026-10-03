#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define HB_TITLE_ID 0x000400000D921E00ULL
#define ARGV_SIZE 0x400

#define DELIVER_SIZE 0x300

static char target[ARGV_SIZE];
static u32 argvBuf[ARGV_SIZE / 4];
static u8 deliver[DELIVER_SIZE];
static size_t deliverSize;

static void fail(const char *fmt, const char *detail)
{
	gfxInitDefault();
	consoleInit(GFX_TOP, NULL);
	printf("\x1b[1;1Hshortcut3ds\n\n");
	printf(fmt, detail);
	printf("\n\nPress START to return to HOME.");
	while (aptMainLoop())
	{
		hidScanInput();
		if (hidKeysDown() & KEY_START)
			break;
		gfxFlushBuffers();
		gfxSwapBuffers();
		gspWaitForVBlank();
	}
	gfxExit();
}

static bool readTarget(void)
{
	FILE *f = fopen("romfs:/target", "rb");
	if (!f)
		return false;
	size_t n = fread(target, 1, sizeof(target) - 1, f);
	fclose(f);
	target[n] = '\0';

	f = fopen("romfs:/deliver", "rb");
	if (f)
	{
		deliverSize = fread(deliver, 1, sizeof(deliver), f);
		fclose(f);
	}
	return target[0] == '/';
}

// Layout read by libctru's argv parser: u32 argc, then NUL-terminated strings.
static void buildArgv(void)
{
	char *out = (char *)&argvBuf[1];
	char *end = (char *)argvBuf + sizeof(argvBuf);
	u32 argc = 0;

	// libctru's romfsMountSelf only accepts an argv[0] that starts with "sdmc:".
	int len = snprintf(out, end - out, "sdmc:%s", target);
	out += len + 1;
	argc++;

	for (char *arg = target + strlen(target) + 1; *arg && out < end; arg += strlen(arg) + 1)
	{
		size_t n = strlen(arg) + 1;
		if (out + n > end)
			break;
		memcpy(out, arg, n);
		out += n;
		argc++;
	}
	argvBuf[0] = argc;
}

static Result hbldrCall(Handle h, u32 cmd, const void *buf, u32 size, u32 bufId)
{
	u32 *cmdbuf = getThreadCommandBuffer();
	cmdbuf[0] = IPC_MakeHeader(cmd, 0, 2);
	cmdbuf[1] = IPC_Desc_StaticBuffer(size, bufId);
	cmdbuf[2] = (u32)buf;
	Result rc = svcSendSyncRequest(h);
	return R_SUCCEEDED(rc) ? (Result)cmdbuf[1] : rc;
}

static bool hbTitleMedia(FS_MediaType *media)
{
	*media = MEDIATYPE_SD;
	if (R_FAILED(amInit()))
		return true;
	u64 id = HB_TITLE_ID;
	AM_TitleEntry entry;
	bool found = R_SUCCEEDED(AM_GetTitleInfo(MEDIATYPE_SD, 1, &id, &entry));
	if (!found && R_SUCCEEDED(AM_GetTitleInfo(MEDIATYPE_NAND, 1, &id, &entry)))
	{
		*media = MEDIATYPE_NAND;
		found = true;
	}
	amExit();
	return found;
}

int main(void)
{
	romfsInit();
	bool ok = readTarget();
	romfsExit();
	if (!ok)
	{
		fail("This shortcut has no target.\n%s", "Make it again with shortcut3ds.");
		return 0;
	}

	char sdPath[ARGV_SIZE + 8];
	snprintf(sdPath, sizeof(sdPath), "sdmc:%s", target);
	struct stat st;
	if (stat(sdPath, &st) != 0)
	{
		fail("Cannot find the app on the SD card:\n\n%s", sdPath);
		return 0;
	}

	FS_MediaType hbMedia;
	if (!hbTitleMedia(&hbMedia))
	{
		fail("%s", "The Homebrew Launcher Loader title\n(000400000D921E00) is not installed.\n\n"
			"Install hblauncher_loader.cia with FBI,\nthen open this shortcut again.");
		return 0;
	}

	Handle hbldr;
	if (R_FAILED(svcConnectToPort(&hbldr, "hb:ldr")))
	{
		fail("%s", "Cannot reach Luma3DS's homebrew loader.\nUpdate Luma3DS, then try again.");
		return 0;
	}

	buildArgv();
	Result rc = hbldrCall(hbldr, 2, target, strlen(target) + 1, 0);
	if (R_SUCCEEDED(rc))
		rc = hbldrCall(hbldr, 3, argvBuf, sizeof(argvBuf), 1);
	svcCloseHandle(hbldr);

	if (R_FAILED(rc))
	{
		char code[16];
		snprintf(code, sizeof(code), "0x%08lX", rc);
		fail("The homebrew loader refused the app.\nError %s", code);
		return 0;
	}

	if (deliverSize)
		aptSetChainloaderArgs(deliver, deliverSize, NULL);
	aptSetChainloader(HB_TITLE_ID, hbMedia);
	return 0;
}
