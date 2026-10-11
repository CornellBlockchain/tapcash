ifeq ($(BOLOS_SDK),)
$(error Environment variable BOLOS_SDK is not set)
endif

include $(BOLOS_SDK)/Makefile.target

APPNAME = "TapCash"
APPVERSION_M = 0
APPVERSION_N = 1
APPVERSION_P = 0
APPVERSION = "$(APPVERSION_M).$(APPVERSION_N).$(APPVERSION_P)"

APP_SOURCE_PATH += src

# Placeholder icons copied from LedgerHQ/app-boilerplate (Apache-2.0)
ICON_STAX = icons/tapcash_32px.gif
ICON_FLEX = icons/tapcash_40px.gif

CURVE_APP_LOAD_PARAMS = secp256k1
PATH_APP_LOAD_PARAMS = "44'/60'"

VARIANT_PARAM = COIN
VARIANT_VALUES = TAPCASH

# Card emulation: the Flex acts as a contactless card, the iPhone is the reader
ENABLE_NFC = 1

#DEBUG = 1

include $(BOLOS_SDK)/Makefile.standard_app
