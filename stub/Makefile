include $(DEVKITARM)/3ds_rules

ARCH := -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft
CFLAGS := -O2 -Wall -Wextra -Werror -mword-relocations -ffunction-sections $(ARCH) -D__3DS__ -I$(CTRULIB)/include
OUT ?= stub.elf

$(OUT): source/main.c
	$(CC) $(CFLAGS) $< -specs=3dsx.specs $(ARCH) -L$(CTRULIB)/lib -lctru -o $@

stub.3dsx: $(OUT)
	3dsxtool $< $@

.PHONY: clean
clean:
	rm -f $(OUT) stub.3dsx
