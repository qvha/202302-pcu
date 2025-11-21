#!/usr/bin/python3
# takes one argument : the current limit, in Ampere

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
NCPU=0

MAILBOX_DATA_OFFSET=0xA0
MAILBOX_INTERFACE_OFFSET=0xA4

# completion codes
PASS                = 0x00
LOCKED              = 0x01
UNSUPPORTED_SERVICE = 0x02
RATIO_EXCEEDS_MAXOC = 0x03
MAX_VOLTAGE         = 0x04
NO_OVERCLOCKING     = 0x05
FIVR_IN_PROGRESS    = 0x06
VR_RAMP_FAILED      = 0x07
VOLT_OVERRIDE_DISABLED = 0x08
INVALID_AVX_LEVEL      = 0x09
INVALID_PARAMETER      = 0x10
UNRECOGNIZED_COMMAND   = 0x1F

# services
IA_CORE       = 0
LLC_AND_RING  = 2
VCC_CFN       = 4
VCC_IO        = 5
VCC_MDFIA     = 6
VCC_MDFI      = 7
VCC_DDRD      = 8
VCC_DDRA      = 9


def wr_ocmailbox(param2, param1, command, data, core=0):
  buffer=struct.pack("IBBBB", data, command, param1, param2, 0b10000000)
  if debug:
    a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", buffer)
    hexa = "{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d,e,f,g,h )
    sys.stdout.write("debug : write to OC_MAILBOX {0}h ( param2={1:02X} "\
                     "param1={2:02X} command={3:02X} data={4:04X} )\n".format(
                     blue(hexa),param2,param1,command,data) )
  try:
    msr.write_mailbox(0x150, 8, buffer, core)
  except:
    sys.stderr.write("Could not write {} to OC_MAILBOX, leaving.\n".format(buffer))
    sys.exit(1)
  return buffer  


def rd_ocmailbox(core=0):
  try:
    chunk=msr.read_mailbox(0x150, 8, core)
  except:
    sys.stderr.write("Could not read the OC_MAILBOX, leaving.\n")
    sys.exit(1)
  if debug:
    a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", chunk)
    hexa = "{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d,e,f,g,h )
    sys.stdout.write("debug : read frm OC_MAILBOX {0}h\n".format( blue(hexa)) )
  return chunk


def mailbox_OC_CAPABILITY(domain):
    wr_chunk=wr_ocmailbox(0,domain,0x01, 0)
    rd_chunk=rd_ocmailbox()
    if debug:
      data,return_code,param1,param2,_=struct.unpack("<IBBBB", rd_chunk)
      sys.stdout.write("{0:02X} {1:02X} {2:02X} {3:02X}\n".format(param2, param1, return_code, data))

    swapped=bitstruct.byteswap("8",rd_chunk)
    return_code,voltage_offset_supported,voltage_overrides_supported,ratio_overclocking_supported,fused= \
      bitstruct.unpack("<p24 u8 p21 b1 b1 b1 u8", swapped)
    if debug:
      sys.stdout.write("chunk  ={0:064b} {0:016X}\n".format(int.from_bytes(rd_chunk  ,"little",signed=False)))
      c="{0:08b}".format(return_code)
      o="{0:01b}".format(voltage_offset_supported)
      v="{0:01b}".format(voltage_overrides_supported)
      r="{0:01b}".format(ratio_overclocking_supported)
      f="{0:08b}".format(fused)

      sys.stdout.write((" "*(24+8)+"{0}"+" "*21+"{1}{2}{3}{4}\n").format(yellow(c),blue(o),red(v),green(r),yellow(f)))
      sys.stdout.write("swapped={0:064b} {0:016X}\n".format(int.from_bytes(swapped,"little",signed=False)))
     
    synthesis=[]
    synthesis.append(
      "Fused max overclocking ratio limit[{0}]={1}".format(domain, yellow("{}".format(fused))))
    if ratio_overclocking_supported:
      synthesis.append(green("ratio overclocking supported"))
    if voltage_overrides_supported:
      synthesis.append(green("voltage overrides supported"))
    if voltage_offset_supported:
      synthesis.append(green("voltage offset supported"))
   
    if len(synthesis)>1:
        for i in range(1,len(synthesis)):
            synthesis[i]="\t"*7+" "*5+synthesis[i]

    print( "{0:24s} {1:016X} → {2:016X} {3}".format(
           "OC_CAPABILITY[{}]".format(domain),
           int.from_bytes(wr_chunk, 'little',signed=False),
           int.from_bytes(rd_chunk, 'little',signed=False),
           "\n".join(synthesis)
           )
         )
    return return_code


def mailbox_PER_CORE_RATIO_LIMITS_CAP(core_index, limits, avx_level):
  """Software may detect per-core ratio limits for overclocking using this read-only mailbox
    service.
    core_index : 0 is 1C to 4C, 1 is 5C to 8C, and so on
    limits     : 0=fused limits ; 1=resolved limits
    avx_level  : 0=IA/SSE, 1=AVX2, 2=AVX3, 3=TMUL
    The command always returns with a passing completion code for legal domains and
    index (param2) settings. Only the IA domain is supported since it is the only domain
    with per-core overclocking ratio constraints. If overclocking is disabled, this service will
    return per-core fused turbo ratio limits. If turbo is disabled, the reported ratios will
    simply reflect the maximum non-turbo ratio.  
  """
  param2=int.from_bytes( bitstruct.pack("b1 u4 p3", limits, avx_level), "little", signed=False)
  wr_chunk=wr_ocmailbox(param2,core_index,0x02, 0)
  rd_chunk=rd_ocmailbox()
  # 63 read busy
  # 55-48 param2
  # 47-40 param1/return_code
  # 39-32 command
  # 31-00 data
  ratio_limit1,ratio_limit2,ratio_limit3,ratio_limit4,return_code,_,_,_= \
    struct.unpack("BBBBBBBB", rd_chunk)
  
  if return_code==9:
    print( "{0:24s} {1:016X} → {2:016X} error=Invalid AVX level {3}".format(
            "PER_CORE_RATIO_LIMITS_CAP()",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            avx_level
            )
          )
  elif return_code==0:
    if limits:  
      stem="RESOLVED RATIO LIM"
    else:  
      stem="FUSED RATIO LIM"
    result=[]
    result.append( stem + "1="+yellow("{}".format(ratio_limit1)))
    result.append( stem + "2="+yellow("{}".format(ratio_limit2)))
    result.append( stem + "3="+yellow("{}".format(ratio_limit3)))
    result.append( stem + "4="+yellow("{}".format(ratio_limit4)))
    for i in 1,2,3 :
      result[i]="\t"*8+result[i]  

    print( "{0:24s} {1:016X} → {2:016X}\t{3}".format(
            "PER_CORE_RATIO_LIMITS_CAP",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            "\n".join(result)
            )
         )
  else:
    pass 
  return return_code


def mailbox_READ_BCLK_FREQUENCY():
  # This command provides the current BCLK frequency in KHz as sampled by the internal controller
  wr_chunk=wr_ocmailbox(0,0,0x05, 0)
  rd_chunk=rd_ocmailbox()
  bclk_frequency,return_code = struct.unpack("<IBxxx", rd_chunk)
  
  if return_code!=0:
    print( "{0:24s} {1:016X} → {2:016X} error={3}".format(
            "READ_BCLK_FREQUENCY",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            return_code
            )
          )
  else:
    value=yellow("{0:.0f}".format(bclk_frequency/1000))
    print( "{0:24s} {1:016X} → {2:016X} BCLK={3}MHz".format(
            "READ_BCLK_FREQUENCY",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            value
            )
         )
  return return_code


def mailbox_READ_OC_STATUS():
  # This command queries the state of some OC knobs and returns an
  # indication if the system is considered “secure”.
  # Note: “Secure” is according to a definition which may change (e.g. harden,
  #       relaxed) in the future
  wr_chunk=wr_ocmailbox(0,0,0x06, 0)
  rd_chunk=rd_ocmailbox()
  swapped=bitstruct.byteswap("8",rd_chunk)
  return_code, status, version = bitstruct.unpack("p24 u8 b1 p23 u8", swapped)
#  version,status,return_code = bitstruct.unpack("<u8 p23 b1 u8 p24", rd_chunk)
  
  if return_code!=0:
    print( "{0:24s} {1:016X} → {2:016X} error={3}".format(
            "READ_OC_STATUS",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            return_code
            )
          )
  else:
    value=yellow("{}".format(version))
    if status:
       status=yellow("{}".format("Safe (secure)")) 
    else:   
       status=yellow("{}".format("Not Secure (some OC was done)")) 
    print( "{0:24s} {1:016X} → {2:016X} version={3} status={4}".format(
            "READ_OC_STATUS",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            value,
            status
            )
         )
  return return_code


def mailbox_READ_FUSED_P0_RATIO(domain, core):
  # This command queries the state of some OC knobs and returns an
  # indication if the system is considered “secure”.
  # Note: “Secure” is according to a definition which may change (e.g. harden,
  #       relaxed) in the future
  wr_chunk=wr_ocmailbox(0,domain,0x07, core)
  rd_chunk=rd_ocmailbox()
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command
  # 31-00 data
  swapped=bitstruct.byteswap("8",rd_chunk)
  return_code, fused_p0_voltage,fused_p0_ratio = \
    bitstruct.unpack("p24 u8 p12 u12 u8", swapped)
  
  if return_code==2:
    print( "{0:24s} {1:016X} → {2:016X} error=No such service in domain {3}".format(
            "READ_FUSED_P0_RATIO[{0}, {1}]".format(domain, core),
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            domain
            )
          )
  elif return_code==5:
    print( "{0:24s} {1:016X} → {2:016X} error=domain {3} not support OC".format(
            "READ_FUSED_P0_RATIO[{0}, {1}]".format(domain, core),
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            domain
            )
          )
  elif return_code==0:
    ratio  =yellow("{}".format(fused_p0_ratio))
    voltage=yellow("{}".format(fused_p0_voltage/2**10))  # U12.2.10V format
    print( "{0:24s} {1:016X} → {2:016X} P0_RATIO={3} P0_VOLTAGE={4} V".format(
            "READ_FUSED_P0_RATIO[{0}, {1}]".format(domain, core),
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            ratio,
            voltage
            )
         )
  else:
    pass 
  return return_code


def mailbox_READ_MISC_GLOBAL_CONF():
  wr_chunk=wr_ocmailbox(0,0,0x14, 0)
  rd_chunk=rd_ocmailbox()
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command
  # 31-00 data
  swapped=bitstruct.byteswap("8",rd_chunk)
  return_code,per_core_vf_override,fivr_efficiency,fivr_faults = \
    bitstruct.unpack("p24 u8 p28 b1 p1 b1 b1", swapped)
  
  if return_code==1:
    print( "{0:24s} {1:016X} → {2:016X} error=Overclocking is locked. This service is read_only".format(
            "READ_MISC_GLOBAL_CONF",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False)
            )
          )
  else:
    if fivr_faults:
        fivr_faults=yellow("DISABLE")
    else:
        fivr_faults=yellow("ENABLE")
  
    if fivr_efficiency:
        fivr_efficiency=yellow("DISABLE")
    else:
        fivr_efficiency=yellow("ENABLE")
  
    if per_core_vf_override:
        per_core_vf_override=yellow("per-core")
    else:
        per_core_vf_override=yellow("all-core")
  
    print( "{0:24s} {1:016X} → {2:016X} FIVR faults                : {3}\n"\
            "\t\t\t\t\t\t\t     Efficiency management      : {4}\n"\
            "\t\t\t\t\t\t\t     Voltage/Frequency override : {5}".format(
            "READ_MISC_GLOBAL_CONF",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False),
            fivr_faults,
            fivr_efficiency,
            per_core_vf_override
            )
         )

  return return_code


def mailbox_READ_AVX_CONTROL():
  wr_chunk=wr_ocmailbox(0,0,0x1A, 0)
  rd_chunk=rd_ocmailbox()
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command
  # 31-00 data
  swapped=bitstruct.byteswap("8",rd_chunk)
  return_code,amx_ratio_offset,avx512_ratio_offset,avx2_ratio_offset = \
    bitstruct.unpack("p24 u8 p12 u5 u5 u5 p5", swapped)
 
  # special exit cases first
  if return_code!=0:
    print( "{0:24s} {1:016X} → {2:016X} Error".format(
            "READ_AVX_CONTROL",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False)
            )
         )
    return return_code

  return_data,_=struct.unpack("II", rd_chunk)
  if return_data==0:
    print( "{0:24s} {1:016X} → {2:016X} This feature is disabled".format(
            "READ_AVX_CONTROL",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False)
            )
         )
    return return_code

  avx2_ratio_offset  =yellow("{}".format(  avx2_ratio_offset))
  avx512_ratio_offset=yellow("{}".format(avx512_ratio_offset))
  amx_ratio_offset   =yellow("{}".format(   amx_ratio_offset))
  print( "{0:24s} {1:016X} → {2:016X} AMX ratio offset = {3}\n"\
          "\t\t\t\t\t\t\t\tAVX512 ratio offset = {4}\n"\
          "\t\t\t\t\t\t\t\t  AVX2 ratio offset = {5}".format(
          "READ_AVX_CONTROL",
          int.from_bytes(wr_chunk, 'little',signed=False),
          int.from_bytes(rd_chunk, 'little',signed=False),
          amx_ratio_offset,
          avx512_ratio_offset,
          avx2_ratio_offset
          )
       )
  return return_code


def mailbox_READ_VF_OVERRIDE(domain):
  wr_chunk=wr_ocmailbox(0,domain,0x10, 0)
  rd_chunk=rd_ocmailbox()
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command
  # 31-00 data
  swapped=bitstruct.byteswap("8",rd_chunk)
  return_code,voltage_offset,voltage_mode,voltage_target,oc_ratio = \
    bitstruct.unpack("p24 u8 u11 b1 u12 u8", swapped)
 
  # special exit cases first
  if return_code!=0:
    print( "{0:24s} {1:016X} → {2:016X} Error".format(
            "READ_VF_OVERRIDE",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False)
            )
         )
    return return_code

  if voltage_mode:
     voltage_mode=yellow("overide")
  else:
     voltage_mode=yellow("adaptive")

  oc_ratio=yellow( "{}".format(oc_ratio))
  voltage_target=yellow( "{}".format(voltage_target))
  voltage_offset=yellow( "{}".format(voltage_offset))
  print( "{0:24s} {1:016X} → {2:016X} OC ratio       = {3}\n"\
          "\t\t\t\t\t\t\t     voltage target = {4}, {6}\n"\
          "\t\t\t\t\t\t\t     voltage offset = {5}".format(
          "READ_VF_OVERRIDE",
          int.from_bytes(wr_chunk, 'little',signed=False),
          int.from_bytes(rd_chunk, 'little',signed=False),
          oc_ratio,
          voltage_target,
          voltage_offset,
          voltage_mode
          )
       )
  return return_code


def mailbox_READ_SVID_CONFIG(svid):
  wr_chunk=wr_ocmailbox(0,svid,0x12, 0)
  rd_chunk=rd_ocmailbox()
  # 63 read busy
  # 55-48 param2
  # 47-40 param1
  # 39-32 command
  # 31-00 data
  swapped=bitstruct.byteswap("8",rd_chunk)
  return_code,lock,voltage_target = \
    bitstruct.unpack("p24 u8 b1 p19 u12", swapped)
 
  # special exit cases first
  if return_code!=0:
    print( "{0:24s} {1:016X} → {2:016X} Error".format(
            "READ_SVID_CONFIG",
            int.from_bytes(wr_chunk, 'little',signed=False),
            int.from_bytes(rd_chunk, 'little',signed=False)
            )
         )
    return return_code

  if lock:
     lock=yellow("SVID disabled")
  else:
     lock=yellow("SVID unlocked")

  voltage_target=yellow("{0:.3f}".format(voltage_target / 2**10 ))
  print( "{0:24s} {1:016X} → {2:016X} voltage_target[{3}]= {4} V  ({5})".format(
          "READ_SVID_CONFIG",
          int.from_bytes(wr_chunk, 'little',signed=False),
          int.from_bytes(rd_chunk, 'little',signed=False),
          svid,
          voltage_target,
          lock
          )
       )
  return return_code


###################################################################################################
#
#  3. main routine that deals with displaying things on the terminal
#     uses "config" (256 bytes) of binary registers to decode,
#     and "registers" a constant array that describes the bitfield
#
###################################################################################################
def update_display(config, registers):
  for offset,text,size, comment in registers:
    reg = bytearray(config[offset:offset+size])
  
    if size==0:
      print( "{0:24s}".format( text ) )
    elif size==1:
      hexa = "{0:02X}".format( reg[0] )
      print( "{0:24s}: {1}h\t\t{2}".format( text, blue(hexa), blue(comment) ) )
    elif size==2:
      if not isinstance(comment, str):
        print( "{0:24s}: {1}".format( text, comment(reg) ) )
      else:  
        a,b = struct.unpack("<BB", reg)
        hexa = "{1:02X}{0:02X}".format( a, b )
        print( "{0:24s}: {1}h\t\t{2}".format( text, blue(hexa), blue(comment) ) )
    elif size==4:
      if not isinstance(comment, str):
        print( "{0:24s}: {1}".format( text, comment(reg) ) )
      else:
        a,b,c,d = struct.unpack("<BBBB", reg)

        hexa = "{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d )
        print( "{0:24s}: {1}\t{2}".format( text, blue(hexa), blue(comment) ) )
    elif size==8:
      if not isinstance(comment, str):
        print( "{0:24s}: {1}".format( text, comment(reg) ) )
      else:  
        a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", reg)
        hexa = "{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d,e,f,g,h )
        print( "{0:24s}: {1}h {2}".format( text, blue(hexa), blue(comment) ) )
  
  

def init():
  # process cntl+C
  # signal.signal(signal.SIGINT, signal_handler)
  global NCPU

  parser = argparse.ArgumentParser(description="Dumps PCU (Power Control Unit) registers, of the first socket, in the first module (by default). Written for Sapphire Rapids.",
           epilog="(c) 2023 HA Quoc Viet" )

  parser.add_argument("--debug",          "-g", action="store_true", default=False)
  parser.add_argument("--current_limit",  "-c", required=True, type=int)
  parser.add_argument("--device", "-d",                      default="0000:7f:1e",
           help="Device to read. Defaults to first module, first socket. "\
           "Use \"lspci -n | grep 3258\" to find yours. "
           "Example : --device 0000:ff:1e" )
  
  # let's read the MSR_RAPL_POWER_UNIT to initialize the fundamental units
  msr.init()
  NCPU=msr.count_cores()
  return parser.parse_args()


###################################################################################################
#
#  2. main function. "init", then works
#
###################################################################################################
def main():
  global debug

#  args=init()
#  debug = args.debug

  for core in range(NCPU):
    comment, \
    idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,iout_offset,min_vid, \
    leak_load_line_r,idle_load_line_r,dynamic_load_line_r = msr.read_VR_MISC_CONFIG( core )

    iout_slope =float(sys.argv[1])
    iout_offset=float(sys.argv[2])

    msr.write_VR_MISC_CONFIG(idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,
                           iout_offset,min_vid, leak_load_line_r,idle_load_line_r,dynamic_load_line_r, core)


if __name__ == '__main__':
  main()
