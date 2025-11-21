#!/usr/bin/python3

import os
import struct
from textwrap import wrap
import bitstruct

from useful_stuff import *


###################################################################################################
#
#  3. PCU CR2 registers (bus:B31, device:30, function: 2)
#     External Design Specification vol 2 : Registers, §18.3 page 5767
#
###################################################################################################
def decode_VID_1_30_2_CFG(reg):
  comment="assigned by PCI-SIG to Intel"  
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_SVID_1_30_2_CFG(reg):
  comment="specifies Intel® but can be set to any value once after reset"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_PACKAGE_RAPL_PERF_STATUS(reg):
  comment="Accumulated time for which PACKAGE was throttled because of "\
          "Package Power limit (RAPL) violations in the "\
          "Platform PBM. Provides information on the performance impact of the RAPL power "\
          "limit. Throttling here is defined as going below OS requested P-state"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  justified=[ "\t\t"+blued[0] ] + [ "\t"*5 + s for s in blued[1:] ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  pwr_limit_throttle_ctr= bitstruct.unpack("u32", reg)[0]
  time="{0:<8.3f}".format(pwr_limit_throttle_ctr*pcu["time_unit"]/2 )
  justified[2]=justified[2].replace('\t\t\t', "\t{0} {1}s\t".format(red("RO"), blue(time) ) )
  return "\n".join(justified)


def decode_DRAM_POWER_INFO_CFG(reg):
  comment="Power allowed for DRAM"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  lock,_,dram_max_win_x,dram_max_win_y,_,dram_max_pwr,_,dram_min_pwr,_,dram_tdp= \
    bitstruct.unpack("b1 u8 u2 u5 b1 u15 b1 u15 b1 u15", reg)
  ro=red("RO")  
  line0="\t\t{0}\n".format(blue(comment))
  line1="  \u251C {0} DRAM MAX WIN = {1} s\t\t{2}\n".format(
           ro, (1+dram_max_win_x/10)*2**dram_max_win_y*pcu["time_unit"], 
           blue("Higher value will be clamped to this value") )
  line2="  \u251C {0} DRAM MAX PWR = {1:3.0f} W\t\t{2}\n".format( 
           ro, dram_max_pwr*pcu["pwr_unit"], blue("Higher value will be clamped to this value") )
  line3="  \u251C {0} DRAM MIN PWR = {1:3.0f} W\t\t{2}\n".format( 
           ro, dram_min_pwr*pcu["pwr_unit"], blue("Reserved, user should ignore this value") )
  line4="  \u2514 {0} DRAM TDP     = {1:3.0f} W\t\t{2}".format(
           ro, dram_tdp*pcu["pwr_unit"], blue("From specifications, not garanteed in real life") )
  return line0+line1+line2+line3+line4


def decode_PROCHOT_RESPONSE_RATIO(reg):
  comment="Controls the CPU response to a prochot or PMAX detector by capping the frequency"
  prochot_ratio,_,_,_= struct.unpack("BBBB", reg)
  return "{0:4d}MHz\t{1}".format(prochot_ratio*100, blue(comment) )


def decode_MEM_TRML_TEMPERATURE_REPORT0(reg):
  comment="used to report the thermal status of the memory. The channel max "\
          "temperature field is used to report the maximal temperature of all ranks"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,channel2_max_temperature,channel1_max_temperature,channel0_max_temperature= \
          struct.unpack("<BBBB", reg)
  ro=red("RO")
  line0="\t\t"+blued[0]+"\n"
  value="{0:>2d}".format(channel2_max_temperature)
  line1="  \u251C {0} CHANNEL 2 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[1])
  value="{0:>2d}".format(channel1_max_temperature)
  line2="  \u251C {0} CHANNEL 1 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[2])
  value="{0:>2d}".format(channel0_max_temperature)
  line3="  \u2514 {0} CHANNEL 0 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  return line0+line1+line2+line3


def decode_MEM_TRML_TEMPERATURE_REPORT1(reg):
  comment="used to report the thermal status of the memory. The channel max "\
          "temperature field is used to report the maximal temperature of all ranks"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,channel2_max_temperature,channel1_max_temperature,channel0_max_temperature= \
          bitstruct.unpack("u8 u8 u8 u8", reg)
  ro=red("RO")
  line0="\t\t"+blued[0]+"\n"
  value="{0:>2d}".format(channel2_max_temperature)
  line1="  \u251C {0} CHANNEL 2 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[1])
  value="{0:>2d}".format(channel1_max_temperature)
  line2="  \u251C {0} CHANNEL 1 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[2])
  value="{0:>2d}".format(channel0_max_temperature)
  line3="  \u2514 {0} CHANNEL 0 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  return line0+line1+line2+line3


def decode_MEM_TRML_TEMPERATURE_REPORT2(reg):
  comment="used to report the thermal status of the memory. The channel max "\
          "temperature field is used to report the maximal temperature of all ranks"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,channel2_max_temperature,channel1_max_temperature,channel0_max_temperature= \
          bitstruct.unpack("u8 u8 u8 u8", reg)
  ro=red("RO")
  line0="\t\t"+blued[0]+"\n"
  value="{0:>2d}".format(channel2_max_temperature)
  line1="  \u251C {0} CHANNEL 2 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[1])
  value="{0:>2d}".format(channel1_max_temperature)
  line2="  \u251C {0} CHANNEL 1 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[2])
  value="{0:>2d}".format(channel0_max_temperature)
  line3="  \u2514 {0} CHANNEL 0 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  return line0+line1+line2+line3


def decode_MEM_TRML_TEMPERATURE_REPORT3(reg):
  comment="used to report the thermal status of the memory. The channel max "\
          "temperature field is used to report the maximal temperature of all ranks"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,channel2_max_temperature,channel1_max_temperature,channel0_max_temperature= \
          bitstruct.unpack("u8 u8 u8 u8", reg)
  ro=red("RO")
  line0="\t\t"+blued[0]+"\n"
  value="{0:>2d}".format(channel2_max_temperature)
  line1="  \u251C {0} CHANNEL 2 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[1])
  value="{0:>2d}".format(channel1_max_temperature)
  line2="  \u251C {0} CHANNEL 1 MAX TEMPERATURE = {1}°C\t{2}\n".format(ro, yellow(value), blued[2])
  value="{0:>2d}".format(channel0_max_temperature)
  line3="  \u2514 {0} CHANNEL 0 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  return line0+line1+line2+line3


def decode_MEM_TRML_TEMPERATURE_REPORT0123(reg):
  comment="used to report the thermal status of the memory. The channel max "\
          "temperature field is used to report the maximal temperature of all ranks"
  wrapped=wrap(comment, 80)
  blued=[ "     "+blue(s) for s in wrapped ]
  mem0_channel0_max_temperature,mem0_channel1_max_temperature,mem0_channel2_max_temperature,_,\
  mem1_channel0_max_temperature,mem1_channel1_max_temperature,mem1_channel2_max_temperature,_,\
  mem2_channel0_max_temperature,mem2_channel1_max_temperature,mem2_channel2_max_temperature,_,\
  mem3_channel0_max_temperature,mem3_channel1_max_temperature,mem3_channel2_max_temperature,_=\
          struct.unpack("BBBBBBBBBBBBBBBB", reg)
  ro=red("RO")
  line0="\nREPORT 0"+" "*70+"REPORT 2\n"

  value="{0:>2d}".format(mem0_channel2_max_temperature)
  line1="   ├ {0} CHANNEL 2 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  value="{0:>2d}".format(mem0_channel1_max_temperature)
  line2="   ├ {0} CHANNEL 1 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  value="{0:>2d}".format(mem0_channel0_max_temperature)
  line3="   └ {0} CHANNEL 0 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  
  value="{0:>2d}".format(mem2_channel2_max_temperature)
  line1+="     {0} CHANNEL 2 MAX TEMPERATURE = {1}°C ┤\n".format(ro, yellow(value))
  value="{0:>2d}".format(mem2_channel1_max_temperature)
  line2+="     {0} CHANNEL 1 MAX TEMPERATURE = {1}°C ┤\n".format(ro, yellow(value))
  value="{0:>2d}".format(mem2_channel0_max_temperature)
  line3+="     {0} CHANNEL 0 MAX TEMPERATURE = {1}°C ┘\n".format(ro, yellow(value))
  
  line4=  "REPORT 1"+" "*70+"REPORT 3\n"

  value="{0:>2d}".format(mem1_channel2_max_temperature)
  line5="   ├ {0} CHANNEL 2 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  value="{0:>2d}".format(mem1_channel1_max_temperature)
  line6="   ├ {0} CHANNEL 1 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  value="{0:>2d}".format(mem1_channel0_max_temperature)
  line7="   └ {0} CHANNEL 0 MAX TEMPERATURE = {1}°C".format(ro, yellow(value))
  
  value="{0:>2d}".format(mem3_channel2_max_temperature)
  line5+="     {0} CHANNEL 2 MAX TEMPERATURE = {1}°C ┤\n".format(ro, yellow(value))
  value="{0:>2d}".format(mem3_channel1_max_temperature)
  line6+="     {0} CHANNEL 1 MAX TEMPERATURE = {1}°C ┤\n".format(ro, yellow(value))
  value="{0:>2d}".format(mem3_channel0_max_temperature)
  line7+="     {0} CHANNEL 0 MAX TEMPERATURE = {1}°C ┘\n".format(ro, yellow(value))
  
  return line0+line1+line2+line3 +line4+ line5+line6+line7+"\n".join(blued)


def decode_DYNAMIC_PERF_POWER_CTL_CFG(reg):
  comment="Governs all major power saving engines and heuristics on the die"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,uncore_perf_plimit_override_enable,active_idle_efficiency_mode,_,imc_apm_override_enable,_= \
    bitstruct.unpack("u11 b1 b1 u8 b1 u10", reg)
  rw=green("RW")  
  if uncore_perf_plimit_override_enable:
    uncore_perf_plimit_override=yellow("Uncore perf limit override ENABLED")
  else:
    uncore_perf_plimit_override=yellow("Uncore perf limit override DISABLED")
  if active_idle_efficiency_mode:
    active_idle_efficiency_mode=yellow("Enables reduction in Socket Power during Active Idle scenarios when Socket EPB = performance")
  else:
    active_idle_efficiency_mode=yellow("Default behavior for Socket EPB = Performance")
  if imc_apm_override_enable:
    imc_apm_override=yellow("imc apm override ENABLED")
  else:
    imc_apm_override=yellow("imc apm override DISABLED")
  line0="\t\t{0}\n".format(blue(comment))
  line1="  \u251C "+rw+" "+uncore_perf_plimit_override+"\n"
  line2="  \u251C "+rw+" "+active_idle_efficiency_mode+"\n"
  line3="  \u2514 "+rw+" "+imc_apm_override
  return line0+line1+line2+line3


def decode_PERF_P_LIMIT_CONTROL_CFG(reg):
  comment="HW does not use the CSR input, it is primarily used by PCODE. Note that "\
          "PERF_P_LIMIT_CLIP must be nominally configured to "\
          "guaranteed frequency + 1, if turbo related actions are needed in slave sockets"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,perf_plimit_differential,_,perf_plimit_clip,_,perf_plimit_threshold,perf_plimit_enable= \
          bitstruct.unpack("u14 u3 u3 u5 b1 u5 b1", reg)
  rw=green("RW")
  if perf_plimit_enable:
    perf_plimit_enable="{}".format(yellow("ENABLED performance P-limit feature"))
  else:
    perf_plimit_enable="{}".format(yellow("DISABLED performance P-limit feature"))

  line0="\t\t"+blued[0]+"\n"
  value="{0:>2d}".format(perf_plimit_differential)
  line1="  \u251C {0} PERF_PLIMIT_DIFFERENTIAL = {1}\t{2}\n".format(rw, yellow(value), blued[2])
  value="{0:>2d}".format(perf_plimit_clip)
  line2="  \u251C {0} PERF_PLIMIT_CLIP         = {1}\t{2}\n".format(
        rw, yellow(value), blue("Maximum value the floor is allowed to be set to for perf P-limit"))
  value="{0:>2d}".format(perf_plimit_threshold)
  line3="  \u251C {0} {1}\n".format(rw, perf_plimit_enable)
  comment="Uncore frequency threshold above which this socket will trigger "\
          "the feature and start trying to raise frequency of other sockets"
  wrapped=wrap(comment, 65)
  line4="  \u2514 {0} PERF_PLIMIT_THRESHOLD    = {1}\t{2}\n\t\t\t\t\t{3}".format(
        rw, yellow(value), blue(wrapped[0]), blue(wrapped[1]))
  return line0+line1+line2+line3+line4

registers= [
  (0x00, "vendor ID"                , 2, decode_VID_1_30_2_CFG ),
  (0x02, "Device ID"                , 2, "RO 325Ah assigned by each IP/function owner as a unique identifier"),
  (0x04, "PCI Command"              , 2, "mostly hardwired to 0"),
  (0x06, "PCI status"               , 2, ""),
  (0x08, "Rev ID & Class code reg." , 8, ""),
  (0x0C, "CACHE LINE SIZE REGISTER" , 1, "size of cache line"),
  (0x0D, "PCI LATENCY TIMER"        , 1, "Not applicable to PCIe. Hardwired to 0"),
  (0x0E, "HEADER TYPE"              , 1, "PCI header type : multi function device, type 0 header"),
  (0x0F, "BUILT IN SELF TEST"       , 1, "Not supported. Hardwired to 0"),
  (0x2C, "Subsystem vendor ID"      , 2, decode_SVID_1_30_2_CFG),
  (0x2E, "Subsystem ID"             , 2, "Assigned to uniquely identify the subsystem"),
  (0x34, "Capability pointer"       , 1, "Points to the first capability structure : the PCIe capability"),
  (0x3C, "Interrupt line"           , 1, "N/A for PCU"),
  (0x3D, "Interrupt pin"            , 1, "N/A for PCU"),
  (0x3E, "Minimum grant"            , 1, "PCI min grant reg : PCU doesn't burst as a PCI compliant master"),
  (0x3F, "Maximum latency"          , 1, "PCU has no specific requirements for how often it accesses PCI"),
  (0x80, "DRAM ENERGY STATUS"       , 4, ""),
  (0x84, "UNCORE FIVR ERROR LOG"    , 4, ""),
  (0x88, "PACKAGE OVERFLOW STATUS"  , 4, decode_PACKAGE_RAPL_PERF_STATUS),
  (0x94, "DTS CONFIGURATION 1"      , 4, ""),
  (0x98, "DTS CONFIGURATION 2"      , 4, ""),
  (0x9C, "DTS CONFIGURATION 3"      , 4, ""),
  (0xA0, "GLOBAL PKG C S CNTRL REG" , 4, ""),
  (0xA4, "GLOBAL NID SOCKET 0\u21923 MAP", 4, ""),
  (0xA8, "DRAM POWER INFORMATION"   , 8, decode_DRAM_POWER_INFO_CFG),
  (0xB0, "PROCHOT RESPONSE RATIO"   , 4, decode_PROCHOT_RESPONSE_RATIO),
# (0xC8, "MEM TRML TEMP. REPORT 0"  , 4, decode_MEM_TRML_TEMPERATURE_REPORT0),
# (0xCC, "MEM TRML TEMP. REPORT 1"  , 4, decode_MEM_TRML_TEMPERATURE_REPORT1),
# (0xD0, "MEM TRML TEMP. REPORT 2"  , 4, decode_MEM_TRML_TEMPERATURE_REPORT2),
# (0xD4, "MEM TRML TEMP. REPORT 3"  , 4, decode_MEM_TRML_TEMPERATURE_REPORT3),
  (0xC8, "   ┌"+"─"*27+" MEM TRML TEMPERATURE "+"─"*28+"┐",16, decode_MEM_TRML_TEMPERATURE_REPORT0123),
  (0xD8, "DRAM PLANE OVERFLOW STATUS", 4, ""),
  (0xDC, "DYNAMIC PERF POWER CTRL"  , 4, decode_DYNAMIC_PERF_POWER_CTL_CFG),
  (0xE4, "PERF P_LIMIT CONTROL"     , 4, decode_PERF_P_LIMIT_CONTROL_CFG),
  (0xE8, "IO BANDWIDTH P_LIMIT CTRL", 4, ""),
  (0xEC, "MCA ERROR SOURCE LOG"     , 4, ""),
  (0xF0, "DRAM PLANE PWR LIMIT CONF", 8, ""),
  (0xF8, "THERMTRIP CONFIGURATION"  , 4, ""),
  (0xFC, "PERFMON PCODE FILTER"     , 4, ""),
]
