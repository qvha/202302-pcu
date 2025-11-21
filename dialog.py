#!/usr/bin/python3

import os
import sys
import time
import struct
from textwrap import wrap
import argparse
import subprocess
import bitstruct

import msr

###################################################################################################
#
#  0. Some constants for internal use
#
###################################################################################################

debug=None

MAILBOX_DATA_OFFSET=0xA0
MAILBOX_INTERFACE_OFFSET=0xA4

# command codes for the OS MAILBOX
CONFIG_TDP     = 0x7F
READ_PM_CONFIG = 0x94
WRITE_PM_CONFIG= 0x95
CLOS           = 0xD0

# sub commands for CONFIG_TDP
GET_LEVELS_INFO          = 0x0
GET_CONFIG_TDP_CONTROL   = 0x1
SET_CONFIG_TDP_CONTROL   = 0x2
GET_TDP_INFO             = 0x3
GET_PWR_INFO             = 0x4
GET_TJMAX_INFO           = 0x5
GET_CORE_MASK            = 0x6
GET_TURBO_LIMIT_RATIOS   = 0x7
SET_LEVEL                = 0x8
GET_UNCORE_P0_P1_INFO    = 0x9
GET_P1_INFO              = 0xa
GET_MEM_FREQ             = 0xb
GET_RATIO_INFO           = 0xc
GET_FACT_HP_TURBO_LIMIT_NUMCORES = 0x10
GET_FACT_HP_TURBO_LIMIT_RATIOS = 0x11
GET_FACT_LP_CLIPPING_RATIO = 0x12
PBF_GET_CORE_MASK_INFO   = 0x20
PBF_GETP1HI_P1LO_INFO    = 0x21
PBF_GET_TJ_MAX_INFO      = 0x22
PBF_GET_TDP_INFO         = 0x23
# subcommands for READ_PM_CONFIG
READ_PM_CONFIG_PM_FEATURE = 0x3
# subcommands for WRITE_PM_CONFIG
WRITE_PM_CONFIG_PM_FEATURE= 0x3
# subcommands for CLOS
CLOS_PM_QOS_CONFIG       = 0x2

###################################################################################################
#
#  1. Some useful routines for later
#
###################################################################################################
def bold(text):
  return '\033[1m'+text+'\033[0m'

def red(text):
  return '\033[31m'+text+'\033[0m'

def blue(text):
  return '\033[34m'+text+'\033[0m'

def yellow(text):
  return '\033[33m'+text+'\033[0m'

def green(text):
  return '\033[32m'+text+'\033[0m'

def magenta(text):
  return '\033[35m'+text+'\033[0m'

def cyan(text):
  return '\033[36m'+text+'\033[0m'

def lightgrey(text):
  return '\033[37m'+text+'\033[0m'

def darkgrey(text):
  return '\033[90m'+text+'\033[0m'

def highlight(text):
  return '\033[43;30m'+text+'\033[0m'

pcu={ "energy_unit": 0,
      "time_unit": 0,
      "pwr_unit": 0
    }

def rdmsr(offset, size ):
  with open("/dev/cpu/0/msr", "rb") as msrfile:
    msrfile.seek(offset)
    return msrfile.read(size)


def mailbox_GET_LEVELS_INFO(fd):
  # This command allows software to discover Intel® SST-PP information.
  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_LEVELS_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( MAILBOX_INTERFACE_OFFSET )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.1)
  fd.seek(MAILBOX_DATA_OFFSET)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  config_tdpe,_,lock,current_config_tdp_level,config_tdp_levels,version=\
          bitstruct.unpack("b1 u6 b1 u8 u8 u8", chunk0)
  result=""       
  if config_tdpe: result=green("CONFIG_TDP is supported")
  else:           result=red  ("CONFIG_TDP is not supported")
  if lock: result+=red  (" TDP level is locked")
  else:    result+=green(" TDP level is unlocked")
  print( "{0:24s} {1}:{2:08X} -> {3:08X}:-------- level={4}/{5} {6}".format(
            "GET_LEVELS_INFO",
            "--------",
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0, 'little',signed=False),
            current_config_tdp_level,
            config_tdp_levels,
            result
            )
        )


def mailbox_GET_TDP_INFO(tdp_level, fd):
  fd.seek( MAILBOX_DATA_OFFSET)

  buffer=bitstruct.pack("u24 u8", 0, tdp_level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_data)

  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_TDP_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_interface)

  time.sleep(.1)
  fd.seek(MAILBOX_DATA_OFFSET)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  _,tdp_ratio,pkg_tdp=bitstruct.unpack("u9 u8 u15", chunk0)
  print( "{0:24s} {1:08X}:{2:08X} -> {3:08X}:-------- TDP_RATIO={4} PKG_TDP={5}W".format( "GET_TDP_INFO[{}]".format(tdp_level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0, 'little',signed=False),
            tdp_ratio,
            pkg_tdp
            )
        )
  

def mailbox_SET_LEVEL(tdp_lock, level, fd):
  # Selects Intel® SST-PP level. BIOS and software must use this mailbox command to
  # select an Intel® SST-PP config level. Activates a specified ConfigTDP level (0, 3 or 4).
  # CPU returns error if the LOCK bit is set in the CONFIG_TDP_CONTROL MSR/CFG
  # register
  buffer=bitstruct.pack("u7 b1 u16 u8", 0, tdp_lock, 0, level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, SET_LEVEL, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( MAILBOX_DATA_OFFSET )
  fd.write(mailbox_data)
  fd.write(mailbox_interface)
  time.sleep(.1)
  fd.seek(MAILBOX_DATA_OFFSET)
  print( "{0:24s} {1:08X}:{2:08X} -> {3:016X} No output".format( "SET_LEVEL({})".format(level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(fd.read(8), 'little',signed=False) ) )


def mailbox_GET_PWR_INFO(tdp_level, fd):  
  # Although there are no new definitions of SKUs for min and max power associated with
  # the new Intel® SST-PP levels, pcode defaults them to the legacy values and supports a
  # notion of min and max power with the new Intel® SST-PP levels.
  fd.seek( MAILBOX_DATA_OFFSET)

  buffer=bitstruct.pack("u24 u8", 0, tdp_level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_data)

  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_PWR_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_interface)

  time.sleep(.1)

  fd.seek(MAILBOX_DATA_OFFSET)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  _,MIN_PWR,MAX_PWR=bitstruct.unpack("u2 u15 u15", chunk0)
  print( "{0:24s} {1:08X}:{2:08X} -> {3:08X}:-------- MIN_PWR={4:3.0f}W MAX_PWR={5:3.0f}W".format(
            "GET_PWR_INFO({})".format(tdp_level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0, 'little',signed=False),
            MIN_PWR/8,
            MAX_PWR/8) )


def mailbox_GET_TJMAX_INFO(tdp_level,fd):  
  # This command allows software to discover the DTS max (also referred as Tprochot or
  # Tjmax) of the selected SST-PP level.
  fd.seek( MAILBOX_DATA_OFFSET)

  buffer=bitstruct.pack("u24 u8", 0, tdp_level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_data) ; fd.flush()

  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_TJMAX_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_interface)

  time.sleep(.1)
  fd.seek(MAILBOX_DATA_OFFSET)
  tjmax=fd.read(1)
  print( "{0:24s} {1:08X}:{2:08X} -> ------{3:02X}:-------- {3}°C".format(
            "GET_TJMAX_INFO({})".format(tdp_level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(tjmax, 'little',signed=False)
            )
        )


def mailbox_READ_PM_CONFIG(pm_feature, fd):
  """This command allows software to discover Intel® SST-CP capability and current state."""  
  buffer=bitstruct.pack("b1 u2 p13 u8 u8", True, 0, pm_feature, READ_PM_CONFIG)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( MAILBOX_INTERFACE_OFFSET )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.1)
  fd.seek(MAILBOX_DATA_OFFSET)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  sst_cp_state,sst_cp_capability=bitstruct.unpack("u16 u16", chunk0)
  if sst_cp_state==1:
    CP_STATE=green("SST CP is enabled")
  else:    
    CP_STATE=red("SST CP is disabled")
  if sst_cp_capability==1:
    CP_CAPABILITY=green("SST CP is supported in HW")
  else:    
    CP_CAPABILITY=red("SST CP is not supported in HW")
  print( "{0:24s} {1}:{2:08X} -> {3:08X}:-------- {4} {5}".format(
            "READ_PM_CONFIG({})".format(pm_feature),
            "--------",
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0,'little',signed=False),
            CP_STATE,
            CP_CAPABILITY
            )
        )



# note pour plus tard  
  """
    # discover the intel sst_pp level
    mailbox_data,mailbox_interface=format_mail(0, CONFIG_TDP, GET_CONFIG_TDP_CONTROL)
    fd.seek( MAILBOX_DATA_OFFSET )
    fd.write(mailbox_data)
    fd.write(mailbox_interface)
    time.sleep(.1)
    fd.seek(MAILBOX_DATA_OFFSET)
    print( "{0:24s} {1:08X}:{2:08X} -> {3:016X}".format( "GET_CONFIG_TDP_CONTROL",
              int.from_bytes(mailbox_data, 'little',signed=False),
              int.from_bytes(mailbox_interface, 'little',signed=False),
              int.from_bytes(fd.read(8), 'little',signed=False) ) )

    # enable/disable SST-BF and/or SST-TF
        mailbox_data,mailbox_interface=format_mail(
            bitstruct.pack("<u17 b1 b1 u14", 0, True, True, 0),
            CONFIG_TDP, SET_CONFIG_TDP_CONTROL)
    fd.seek( MAILBOX_DATA_OFFSET )
    fd.write(mailbox_data)
    fd.write(mailbox_interface)
    time.sleep(.1)
    fd.seek(MAILBOX_DATA_OFFSET)
    print( "{0:24s} {1:08X}:{2:08X} -> {3:016X}".format( "GET_LEVELS_INFO",
              int.from_bytes(mailbox_data, 'little',signed=False),
              int.from_bytes(mailbox_interface, 'little',signed=False),
              int.from_bytes(fd.read(8), 'little',signed=False) ) )
"""
###################################################################################################
#
#  2. Everybody deserves an initialisation step
#
###################################################################################################
def init():

  parser = argparse.ArgumentParser(description="Attempts a dialog with the PCU through its mailbox",
           epilog="(c) 2023 HA Quoc Viet" )

  parser.add_argument("--debug",  "-g", action="store_true", default=False)
  
  # discover where the PCUs are
  # dirty version using lspci. don't blame me, I have 10min before a meeting
  PCUTable=[]
  commande=[ "lspci", "-s", "1e.0" ] 
  p=subprocess.Popen( commande, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True )
  # typical output, here on 8S :
  #0000:3f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0000:7f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0000:bf:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0000:ff:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:3f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:7f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:bf:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:ff:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  for dataline in p.stdout:
    if dataline.strip("\n ") == "": continue
    PCUTable.append( dataline.split()[0][:-2] )  # cutting ".0" out
  # [ "0000:3f:1e", "0000:7f:1e", .... ]
  return parser.parse_args(),PCUTable


###################################################################################################
#
#  3. main function. "init", then works
#
###################################################################################################
def main():
  global debug

  args,PCUTable=init()
  debug = args.debug

  # hardcoded to CPU0 and RC1
  with open("/sys/bus/pci/devices/{0}.1/config".format(PCUTable[0]),"r+b", buffering=0) as fd:

    mailbox_GET_LEVELS_INFO(fd)
    mailbox_GET_TDP_INFO(0, fd)
    # get info for each TDP levels
    mailbox_GET_TJMAX_INFO(0,fd)  
    mailbox_GET_PWR_INFO(0,fd)
    mailbox_GET_PWR_INFO(3,fd)
    mailbox_GET_PWR_INFO(4,fd)
    mailbox_SET_LEVEL(False, 0, fd)
    mailbox_GET_LEVELS_INFO(fd)
    mailbox_GET_PWR_INFO(0,fd)
    mailbox_GET_PWR_INFO(3,fd)
    mailbox_GET_PWR_INFO(4,fd)
    mailbox_SET_LEVEL(False, 3, fd)
    mailbox_GET_LEVELS_INFO(fd)
    mailbox_GET_PWR_INFO(0,fd)
    mailbox_GET_PWR_INFO(3,fd)
    mailbox_GET_PWR_INFO(4,fd)
    mailbox_SET_LEVEL(False, 4, fd)
    mailbox_GET_LEVELS_INFO(fd)
    mailbox_GET_PWR_INFO(0,fd)
    mailbox_GET_PWR_INFO(3,fd)
    mailbox_GET_PWR_INFO(4,fd)

    print('-'*15 + " second take " + '-'*15)
# EDS p182 10.6.2 Config TDP 1 and 2 functionality
# 1. The BIOS/SW discovers Intel® SST-PP capability via GET_LEVELS_INFO mailbox
    mailbox_GET_LEVELS_INFO(fd)
# 2. The BIOS/SW can discover the P1 ratios via GET_P1_INFO mailbox. Note that the
#    configuration index supported are 0, 3 and 4. (the 0, 1 and 2 performance levels
#    previously used are now combined to provided ratios for SSE, Intel® AVX2 and
#    Intel® AVX3)
    mailbox_GET_PWR_INFO(0,fd)
# 3. The BIOS/SW writes the P1 ratio via FLEX_RATIO MSR.
    msr.read_VR_CURRENT_CONFIG(core=0)
    msr.read_FLEX_RATIO(core=0)
    # OC_lock=False ocbins=0 flexenable=True flexratio=23  246mV 
    msr.write_FLEX_RATIO(False,0,True,23,246,core=0)
    msr.read_FLEX_RATIO(core=0)
# 4. The BIOS/SW writes the min ICCP [SST-CP] license to pre-grant a license using the
#    WRITE_PM_CONFIG mailbox.
    mailbox_READ_PM_CONFIG(0, fd)
    mailbox_READ_PM_CONFIG(1, fd)
    mailbox_READ_PM_CONFIG(2, fd)
    mailbox_READ_PM_CONFIG(3, fd)

if __name__ == '__main__':
  main()
