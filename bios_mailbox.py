#!/usr/bin/python3
# use --debug


# qvha 202501 : pausing development on the BIOS MAILBOX code, as reading MSR 607h results in
# an os.error(), whether 4 bytes or 8 bytes.
# i have tried to find a lock in bios settings using ("mailbox", "B2P", "lock", "mbox" keywords)
# i have tried to find a lock in the EDS (this coudl be improved)
# now i beleive that the whole infrastructure is locked.
# the last hope i can see, is to access it through MMIO instead.
# actually, just found out is accessible through PCU RC1
# through PCU_RC1, I have looped on the OC_INTERFACE and all that is coming back, is zero. 
import os
import sys
import time
import math
import struct
from textwrap import wrap
import argparse
import subprocess
import bitstruct

from useful_stuff import *
import msr

###################################################################################################
#
#  0. Some constants for internal use
#
###################################################################################################

debug=None
NCPU=msr.count_cores()

# MMIO interface ; currently not understood / unused
BIOS_MAILBOX_DATA=0x8C
BIOS_MAILBOX_INTERFACE=0x90

# completion codes
PASS                = 0x00
ILLEGAL_COMMAND     = 0x01
TIMEOUT             = 0x02
#ILLEGAL_DATA        = 0x03
ILLEGAL_DATA        = 0x04
ILLEGAL_VR_ID       = 0x05
VR_INTERFACE_LOCKED = 0x06
TSC_COMMAND_LOCKED  = 0x06
VR_ERROR            = 0x07
ILLEGAL_SUB_COMMAND = 0x08
EDRAM_NOT_FUNCTIONAL= 0x09
EDRAM_UNAVAILABLE   = 0x10

# Commands
SVID_VR      = 0x18
OC_INTERFACE = 0x37

############## OS MAILBOX ########################################################################
OS_MAILBOX_DATA=0xA0
OS_MAILBOX_INTERFACE=0xA4

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
#  1. Some mailbox utilities
#     None of these have been confirmed to work, as it is likely
#     that the whole msr 607h is locked out
#
###################################################################################################

def read(core=0):
  """
     Read command, param1, param2 at MSR 607h
     data at 608h
     MSR are speudo files, where the user is supposed to seek to the msr number as offset,
     then read a chunk of 8 bytes. Reading less can lead to an error. 
     the msr number are not really offsets into a file, as 64 bit registers can follow
     sequencially (example MSR 580h and 581h, all the while 32 bits MSR can also follow
     sequentially. Hence, follow stricly the protocol : seek(msr), read(8).
     returns the bytes straight from fd.read(4)
  """
  mailbox_interface = 0x607                    # hardcoded interface MSR
  mailbox_data      = 0x608                    # hardcoded data MSR
  msrfile="/dev/cpu/{0:d}/msr".format(core)    # where is it mapped

  with open(msrfile, "rb") as fd:
    # we poll on the last bit
    count=0
    while count<20:
      fd.seek(mailbox_interface)               # absolute positioning by default
      chunk=fd.read(4)
      if int.from_bytes(chunk, "little", signed=False)>>31 :
        time.sleep(.1)                         # typical latency is 3 micro second per request
      else: break
      count+=1
    # end while  
    if count>=20:
      sys.stderr.write("Could not read the BIOS_MAILBOX, leaving.\n")
      sys.exit(1)
    # general case  
    chunk_interface=chunk
    fd.seek(mailbox_data)
    chunk_data=fd.read(4)
      
  return chunk_interface, chunk_data



def write(param2, param1, command, data, core=0):
  """
     Write command, param1, param2 at MSR 607h
     Write data at 608h
     MSR are speudo files, where the user is supposed to seek to the msr number as offset,
     then read a chunk of 8 bytes. Reading less can lead to an error. 
     the msr number are not really offsets into a file, as 64 bit registers can follow
     sequencially (example MSR 580h and 581h, all the while 32 bits MSR can also follow
     sequentially. Hence, follow stricly the protocol : seek(msr), read(size).
  """
  mailbox_interface = 0x607                    # hardcoded interface MSR
  mailbox_data      = 0x608                    # hardcoded data MSR
  msrfile="/dev/cpu/{0:d}/msr".format(core)    # where is it mapped

  with open(msrfile, "r+b") as fd:             # w+ erases, then opens. r+ opens for reading and writing 
    # we poll on the last bit
    count=0
    while count<20:
      fd.seek(mailbox_interface)
      chunk=fd.read(4)                         # 4 fails. 8 fails. am giving up on the BIOS_MAILBOX, until i find out how to "unlock" it
      if int.from_bytes(chunk, "little", signed=False)>>31 : time.sleep(.1)
      else: break
      count+=1
    # end while  
    if count>=20:
      sys.stderr.write("Could not write {} to BIOS_MAILBOX, leaving.\n".format(buffer))
      sys.exit(1)
    # general case  
    buffer=struct.pack("I", data)
    fd.seek(mailbox_data)                      # absolute positioning to mailbox data MSR
    fd.write(buffer)
    buffer=struct.pack("BBBB", command, param1, param2, 0b10000000)
    fd.seek(mailbox_interface)                 # absolute positioning to mailbox interface MSR
    fd.write(buffer)

  # some debug on the terminal
  if debug:
    a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", buffer)
    hexa = "{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d,e,f,g,h )
    sys.stdout.write("debug : write to BIOS_MAILBOX {0}h ( param2={1:02X} "\
                     "param1={2:02X} command={3:02X} data={4:04X} )\n".format(
                     blue(hexa),param2,param1,command,data) )
  return



def wr_biosmailbox(param2, param1, command, data, core=0):
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command / return code
  # 31-00 data
  # "I" is unsigned int size 4 bytes, for data
  buffer =struct.pack("BBBBI", command, param1, param2, 0b10000000, data)
  try:
    msr.write_mailbox(0x607, 8, buffer, core)
  except:
    sys.stderr.write("Could not write {} to OC_MAILBOX, leaving.\n".format(buffer))
    sys.exit(1)


def rd_biosmailbox(core=0):
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command / return code
  # 31-00 data
  try:
    chunk=msr.read_mailbox(0x607, 8, core)
  except:
    sys.stderr.write("Could not read the BIOS_MAILBOX, leaving.\n")
    sys.exit(1)
  if debug:
    a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", chunk)
    hexa = "{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d,e,f,g,h )
    sys.stdout.write("debug : read frm BIOS_MAILBOX {0}h\n".format( blue(hexa)) )
  return chunk


###################################################################################################
#
#  2. BIOS mailbox commands
#
###################################################################################################

# All VR configurations on Ice Lake processor are achieved through the BIOS mailbox
# interface VR handler command described in Section 4.12.6. Specifically for Running
# Average Current limit monitor and control the sub-commands 0x5, 0x6 (Get/Set
# IccMax) and 0x19, 0x1A (Get/Set VR TDC) are used
# 627270 Alder Lake, Raptor Lake, Twin Lake, Core and Uncore BIOS specification, rev 1.0.5i, page 45

# SVID VR handler command 0x18 : sub command 0x0
def GET_STRAP_CONFIGURATION(fd):
  buffer=bitstruct.pack("b1 p2 p13 u8 u8", True, 0, SVID_VR)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( BIOS_MAILBOX_INTERFACE )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.01)

  fd.seek( BIOS_MAILBOX_INTERFACE )
  rd_chunk_interface=bitstruct.byteswap("4",fd.read(4))
  # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
  return_code=struct.unpack("xxxB", rd_chunk_interface)[0]

  fd.seek( BIOS_MAILBOX_DATA )
  rd_chunk_data=bitstruct.byteswap("4",fd.read(4))
  # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
  strap_config=bitstruct.unpack("p30 u2", rd_chunk_data)[0]


  # special exit cases first
  table=[ "resolved VR configuration",
          "RAW VR configuration from CPU strap",
          "Resolved value of CPU strap High",
          "RAW value from CPU strap High"
        ]
  if return_code!=0:
    result="unknown error code"
  else:
    # general case
    result=table[strap_config]

  print( "{0:24s} {1}:{2:08X} → {3:08X}:{4:08X} strap_config={5} ({6})".format(
            "GET_STRAP_CONFIGURATION",
            "--------",
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(rd_chunk_data,     'little',signed=False),
            int.from_bytes(rd_chunk_interface,'little',signed=False),
            strap_config,
            result
            )
       )
  return strap_config


# SVID VR handler command 0x18 : sub command 0x1
def GET_ACDC_LOADLINE(fd):
  buffer=bitstruct.pack("b1 p2 p13 u8 u8", True, 1, SVID_VR)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( BIOS_MAILBOX_INTERFACE )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.01)

  fd.seek( BIOS_MAILBOX_INTERFACE )
  rd_chunk_interface=bitstruct.byteswap("4",fd.read(4))
  # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
  return_code=struct.unpack("xxxB", rd_chunk_interface)[0]

  fd.seek( BIOS_MAILBOX_DATA )
  rd_chunk_data=bitstruct.byteswap("4",fd.read(4))
  # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
  dc_loadline,ac_loadline=bitstruct.unpack("u16 u16", rd_chunk_data)

  factor=math.pow(2,20)
  dc_loadline/=factor
  ac_loadline/=factor

  print( "{0:24s} {1}:{2:08X} → {3:08X}:{4} ac_loadline={5}mΩ dc_loadline={6}mΩ".format(
            "GET_ACDC_LOADLINE",
            "--------",
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(rd_chunk_data,     'little',signed=False),
            "--------",
            ac_loadline,
            dc_loadline
            )
       )
  return ac_loadline,dc_loadline

# SVID VR blindly launch all functions, looking for non zero output
def SVIDVRloop(fd):
  for n in [ (SVID_VR,0),(SVID_VR,1), (SVID_VR,5), (SVID_VR,7), (SVID_VR,9), (SVID_VR,0xA), (SVID_VR,0x13), (SVID_VR,0x18), (SVID_VR,0x1C), (SVID_VR,0x24),
             (0x19,0), ( 0x19,1),( 0x19,2),( 0x19,3),( 0x19,4),( 0x19,5),( 0x19,6),( 0x19,7),( 0x19,8),
             (0x37,4),
             (0x50,0), (0x1C, 0), (0x1F,0),
             (0x2E,0),(0x2E,1),(0x2E,2),(0x2E,3)]:  
    command,sub_command = n  
    buffer=bitstruct.pack("b1 p2 p13 u8 u8", True, sub_command, command)
    mailbox_interface=bitstruct.byteswap("4",buffer)
    fd.seek( BIOS_MAILBOX_INTERFACE )
    fd.write(mailbox_interface) ; fd.flush()
    time.sleep(.01)
  
    fd.seek( BIOS_MAILBOX_INTERFACE )
    rd_chunk_interface=bitstruct.byteswap("4",fd.read(4))
    # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
    return_code=struct.unpack("xxxB", rd_chunk_interface)[0]
  
    fd.seek( BIOS_MAILBOX_DATA )
    rd_chunk_data=bitstruct.byteswap("4",fd.read(4))
    # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
    # dc_loadline,ac_loadline=bitstruct.unpack("u16 u16", rd_chunk_data)
  
    print( "{0:24s} {1}:{2:08X} → {3:08X}:{4:08X}".format(
              "READ [{},{}]".format(command,sub_command),
              "--------",
              int.from_bytes(mailbox_interface, 'little',signed=False),
              int.from_bytes(rd_chunk_data,     'little',signed=False),
              int.from_bytes(rd_chunk_interface,'little',signed=False)
              )
         )
  return


# OC_INTERFACE command 0x37
# This command allows setting and reading various Overclocking controls.
# 819915 Arrow Lake PTG June 2024

# OC_INTERFACE command 0x37 : sub command 0x0
def READ_OC_MISC_CONFIG(fd):
  for sub_command in [ 0, 2, 4, 6, 8, 0x12, 0x16, 0x18, 0x1A ]:
    buffer=bitstruct.pack("b1 p2 p13 u8 u8", True, sub_command, OC_INTERFACE)
    mailbox_interface=bitstruct.byteswap("4",buffer)
    fd.seek( BIOS_MAILBOX_INTERFACE )
    fd.write(mailbox_interface) ; fd.flush()
    time.sleep(.01)
  
    fd.seek( BIOS_MAILBOX_INTERFACE )
    rd_chunk_interface=bitstruct.byteswap("4",fd.read(4))
    # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
    return_code=struct.unpack("xxxB", rd_chunk_interface)[0]
  
    fd.seek( BIOS_MAILBOX_DATA )
    rd_chunk_data=bitstruct.byteswap("4",fd.read(4))
    # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
    # dc_loadline,ac_loadline=bitstruct.unpack("u16 u16", rd_chunk_data)
  
    print( "{0:24s} {1}:{2:08X} → {3:08X}:{4:08X}".format(
              "READ_OC-{}".format(sub_command),
              "--------",
              int.from_bytes(mailbox_interface, 'little',signed=False),
              int.from_bytes(rd_chunk_data,     'little',signed=False),
              int.from_bytes(rd_chunk_interface,'little',signed=False)
              )
         )
  return

###################################################################################################
#
#  2bis. OS MAILBOX commands
#
###################################################################################################

def os_mailbox_GET_LEVELS_INFO(fd):
  # This command allows software to discover Intel® SST-PP information.
  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_LEVELS_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( OS_MAILBOX_INTERFACE )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.1)
  fd.seek(OS_MAILBOX_DATA)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  config_tdpe,_,lock,current_config_tdp_level,config_tdp_levels,version=\
          bitstruct.unpack("b1 u6 b1 u8 u8 u8", chunk0)
  result=""       
  if config_tdpe: result=green("CONFIG_TDP is supported")
  else:           result=red  ("CONFIG_TDP is not supported")
  if lock: result+=red  (" TDP level is locked")
  else:    result+=green(" TDP level is unlocked")
  print( "{0:24s} {1}:{2:08X} → {3:08X}:-------- level={4}/{5} {6}".format(
            "GET_LEVELS_INFO",
            "--------",
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0, 'little',signed=False),
            current_config_tdp_level,
            config_tdp_levels,
            result
            )
        )


def os_mailbox_GET_TDP_INFO(tdp_level, fd):
  fd.seek( OS_MAILBOX_DATA)

  buffer=bitstruct.pack("u24 u8", 0, tdp_level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_data)

  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_TDP_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_interface)

  time.sleep(.1)
  fd.seek(OS_MAILBOX_DATA)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  _,tdp_ratio,pkg_tdp=bitstruct.unpack("u9 u8 u15", chunk0)
  print( "{0:24s} {1:08X}:{2:08X} → {3:08X}:-------- TDP_RATIO={4} PKG_TDP={5}W".format( "GET_TDP_INFO[{}]".format(tdp_level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0, 'little',signed=False),
            tdp_ratio,
            pkg_tdp
            )
        )
  

def os_mailbox_SET_LEVEL(tdp_lock, level, fd):
  # Selects Intel® SST-PP level. BIOS and software must use this mailbox command to
  # select an Intel® SST-PP config level. Activates a specified ConfigTDP level (0, 3 or 4).
  # CPU returns error if the LOCK bit is set in the CONFIG_TDP_CONTROL MSR/CFG
  # register
  buffer=bitstruct.pack("u7 b1 u16 u8", 0, tdp_lock, 0, level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, SET_LEVEL, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( OS_MAILBOX_DATA )
  fd.write(mailbox_data)
  fd.write(mailbox_interface)
  time.sleep(.1)
  fd.seek(OS_MAILBOX_DATA)
  print( "{0:24s} {1:08X}:{2:08X} → {3:016X} No output".format( "SET_LEVEL({})".format(level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(fd.read(8), 'little',signed=False) ) )


def os_mailbox_GET_PWR_INFO(tdp_level, fd):  
  # Although there are no new definitions of SKUs for min and max power associated with
  # the new Intel® SST-PP levels, pcode defaults them to the legacy values and supports a
  # notion of min and max power with the new Intel® SST-PP levels.
  fd.seek( OS_MAILBOX_DATA)

  buffer=bitstruct.pack("u24 u8", 0, tdp_level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_data)

  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_PWR_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_interface)

  time.sleep(.1)

  fd.seek(OS_MAILBOX_DATA)
  chunk0=bitstruct.byteswap("4",fd.read(4))
  _,MIN_PWR,MAX_PWR=bitstruct.unpack("u2 u15 u15", chunk0)
  print( "{0:24s} {1:08X}:{2:08X} → {3:08X}:-------- MIN_PWR={4:3.0f}W MAX_PWR={5:3.0f}W".format(
            "GET_PWR_INFO({})".format(tdp_level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(chunk0, 'little',signed=False),
            MIN_PWR/8,
            MAX_PWR/8) )


def os_mailbox_GET_TJMAX_INFO(tdp_level,fd):  
  # This command allows software to discover the DTS max (also referred as Tprochot or
  # Tjmax) of the selected SST-PP level.
  fd.seek( OS_MAILBOX_DATA)

  buffer=bitstruct.pack("u24 u8", 0, tdp_level)
  mailbox_data=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_data) ; fd.flush()

  buffer=bitstruct.pack("b1 u2 u21 u8", True, 0, GET_TJMAX_INFO, CONFIG_TDP)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.write(mailbox_interface)

  time.sleep(.1)
  fd.seek(OS_MAILBOX_DATA)
  tjmax=fd.read(1)
  print( "{0:24s} {1:08X}:{2:08X} → ------{3:02X}:-------- {3}°C".format(
            "GET_TJMAX_INFO({})".format(tdp_level),
            int.from_bytes(mailbox_data, 'little',signed=False),
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(tjmax, 'little',signed=False)
            )
        )



def READ_TJMAX_OVERRIDE(fd):  
  # A new knob for Tjmax temp to be programmable. This will allow BIOS mailbox command
  # to program Tjmax temp via BIOS knob.
  # New BIOS mailbox command required. BIOS will use the BIOS to pCode mail box
  # command to change the Tjmax temp value. 
  # 751210 SPR PTG 3.1.1.2.1 Tjmax temp overide
  buffer=bitstruct.pack("b1 p2 p13 u8 u8", True, 0, 0xA5)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( BIOS_MAILBOX_INTERFACE )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.01)

  fd.seek( BIOS_MAILBOX_INTERFACE )
  rd_chunk_interface=bitstruct.byteswap("4",fd.read(4))
  # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
  return_code=struct.unpack("xxxB", rd_chunk_interface)[0]

  fd.seek( BIOS_MAILBOX_DATA )
  rd_chunk_data=bitstruct.byteswap("4",fd.read(4))
  # <<<HSB       p padding   b boolean   u unsigned int   s signed int    LSB<<<
  # dc_loadline,ac_loadline=bitstruct.unpack("u16 u16", rd_chunk_data)

  print( "{0:24s} {1}:{2:08X} → {3:08X}:{4:08X}".format(
            "READ TJMAX_OVERRIDE",
            "--------",
            int.from_bytes(mailbox_interface, 'little',signed=False),
            int.from_bytes(rd_chunk_data,     'little',signed=False),
            int.from_bytes(rd_chunk_interface,'little',signed=False)
            )
       )



def os_mailbox_READ_PM_CONFIG(pm_feature, fd):
  """This command allows software to discover Intel® SST-CP capability and current state."""  
  buffer=bitstruct.pack("b1 u2 p13 u8 u8", True, 0, pm_feature, READ_PM_CONFIG)
  mailbox_interface=bitstruct.byteswap("4",buffer)
  fd.seek( OS_MAILBOX_INTERFACE )
  fd.write(mailbox_interface) ; fd.flush()
  time.sleep(.1)
  fd.seek(OS_MAILBOX_DATA)
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
  print( "{0:24s} {1}:{2:08X} → {3:08X}:-------- {4} {5}".format(
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
    fd.seek( OS_MAILBOX_DATA )
    fd.write(mailbox_data)
    fd.write(mailbox_interface)
    time.sleep(.1)
    fd.seek(OS_MAILBOX_DATA)
    print( "{0:24s} {1:08X}:{2:08X} → {3:016X}".format( "GET_CONFIG_TDP_CONTROL",
              int.from_bytes(mailbox_data, 'little',signed=False),
              int.from_bytes(mailbox_interface, 'little',signed=False),
              int.from_bytes(fd.read(8), 'little',signed=False) ) )

    # enable/disable SST-BF and/or SST-TF
        mailbox_data,mailbox_interface=format_mail(
            bitstruct.pack("<u17 b1 b1 u14", 0, True, True, 0),
            CONFIG_TDP, SET_CONFIG_TDP_CONTROL)
    fd.seek( OS_MAILBOX_DATA )
    fd.write(mailbox_data)
    fd.write(mailbox_interface)
    time.sleep(.1)
    fd.seek(OS_MAILBOX_DATA)
    print( "{0:24s} {1:08X}:{2:08X} → {3:016X}".format( "GET_LEVELS_INFO",
              int.from_bytes(mailbox_data, 'little',signed=False),
              int.from_bytes(mailbox_interface, 'little',signed=False),
              int.from_bytes(fd.read(8), 'little',signed=False) ) )
"""
###################################################################################################
#
#  3. Init.
#     Everybody deserves an init
#     Returns a namespace
#
###################################################################################################
def init():
  # process cntl+C
  # signal.signal(signal.SIGINT, signal_handler)

  parser = argparse.ArgumentParser(description="Explores the BIOS mailbox. Written for Sapphire Rapids"\
           "from raptor lake Core and Uncore bios spec 627270.",
           epilog="(c) 2025 BULL SAS, "
                  "HA Quoc Viet <quoc-viet.ha@eviden.com>" )

  parser.add_argument("--debug",  "-g", action="store_true", default=False)
  parser.add_argument("--device", "-d",                      default="0000:7f:1e",
           help="Device to read. Defaults to first module, first socket. "\
           "Use \"lspci -n | grep 3258\" to find yours. "
           "Example : --device 0000:ff:1e" )
  
  # let's read the MSR_RAPL_POWER_UNIT to initialize the fundamental units
  msr.init()

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
if __name__ == '__main__':

  args,PCUTable=init()
  debug = args.debug

  # hardcoded to CPU0 and RC1
  with open("/sys/bus/pci/devices/{0}.1/config".format(PCUTable[0]),"r+b", buffering=0) as fd:
    """
    os_mailbox_GET_LEVELS_INFO(fd)
    os_mailbox_GET_TDP_INFO(0, fd)
    # get info for each TDP levels
    os_mailbox_GET_TJMAX_INFO(0,fd)  
    os_mailbox_GET_PWR_INFO(0,fd)
    os_mailbox_GET_PWR_INFO(3,fd)
    os_mailbox_GET_PWR_INFO(4,fd)
    os_mailbox_SET_LEVEL(False, 0, fd)
    os_mailbox_GET_LEVELS_INFO(fd)
    os_mailbox_GET_PWR_INFO(0,fd)
    os_mailbox_GET_PWR_INFO(3,fd)
    os_mailbox_GET_PWR_INFO(4,fd)
    os_mailbox_SET_LEVEL(False, 3, fd)
    os_mailbox_GET_LEVELS_INFO(fd)
    os_mailbox_GET_PWR_INFO(0,fd)
    os_mailbox_GET_PWR_INFO(3,fd)
    os_mailbox_GET_PWR_INFO(4,fd)
    os_mailbox_SET_LEVEL(False, 4, fd)
    os_mailbox_GET_LEVELS_INFO(fd)
    os_mailbox_GET_PWR_INFO(0,fd)
    os_mailbox_GET_PWR_INFO(3,fd)
    os_mailbox_GET_PWR_INFO(4,fd)

    print('-'*15 + " second take " + '-'*15)
# EDS p182 10.6.2 Config TDP 1 and 2 functionality
# 1. The BIOS/SW discovers Intel® SST-PP capability via GET_LEVELS_INFO mailbox
    os_mailbox_GET_LEVELS_INFO(fd)
# 2. The BIOS/SW can discover the P1 ratios via GET_P1_INFO mailbox. Note that the
#    configuration index supported are 0, 3 and 4. (the 0, 1 and 2 performance levels
#    previously used are now combined to provided ratios for SSE, Intel® AVX2 and
#    Intel® AVX3)
    os_mailbox_GET_PWR_INFO(0,fd)
# 3. The BIOS/SW writes the P1 ratio via FLEX_RATIO MSR.
    msr.read_VR_CURRENT_CONFIG(core=0)
    msr.read_FLEX_RATIO(core=0)
    # OC_lock=False ocbins=0 flexenable=True flexratio=23  246mV 
    msr.write_FLEX_RATIO(False,0,True,23,246,core=0)
    msr.read_FLEX_RATIO(core=0)
# 4. The BIOS/SW writes the min ICCP [SST-CP] license to pre-grant a license using the
#    WRITE_PM_CONFIG mailbox.
    os_mailbox_READ_PM_CONFIG(0, fd)
    os_mailbox_READ_PM_CONFIG(1, fd)
    os_mailbox_READ_PM_CONFIG(2, fd)
    os_mailbox_READ_PM_CONFIG(3, fd)
    """
# 5. Investigating the BIOS mailbox
    GET_STRAP_CONFIGURATION(fd)
    GET_ACDC_LOADLINE(fd)
    READ_OC_MISC_CONFIG(fd)
    SVIDVRloop(fd)
    print("RPL PTG 747256 : read/write tjmaxoffset p79 9.26.2 BIOS MAIL BOX COMMAND")
    READ_TJMAX_OVERRIDE(fd)
    # CF RPL PTG 747256 page 79 9.26.2
    # i am trying to change tj max offset 
    # for which msr 1A2h will show the actual effect of the bios_mailbox
    msr.read_TEMPERATURE_TARGET(0)
