#!/usr/bin/python3

import os
import struct
from textwrap import wrap
import argparse
import bitstruct

from useful_stuff import *


###################################################################################################
#
#  4. PCU CR3 registers (bus:B31, device:30, function: 3)
#     External Design Specification vol 2 : Registers, §18.4 page 5789
#
###################################################################################################
def decode_VID_1_30_3_CFG(reg):
  comment="assigned by PCI-SIG to Intel"  
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_SVID_1_30_3_CFG(reg):
  comment="specifies Intel® but can be set to any value once after reset"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_CONFIG_TDP_LEVEL1(reg):
  comment="Level 1 configurable TDP settings"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,pkg_min_pwr,pkg_max_pwr,_,tdp_ratio,_,pkg_tdp= \
    bitstruct.unpack("b1 u16 u15 u8 u8 b1 u15", reg)
  ro=red("RO")  
  line0="\t\t{0}\n".format(blue(comment))
  value="{0}".format(pkg_min_pwr*pcu["pwr_unit"])         
  line1="  \u251C {0} PKG MIN PWR = {1} W\t\t{2}\n".format(
           ro, yellow(value), 
           blue("Min pkg power setting allowed for this level") )
  value="{0}".format(pkg_max_pwr*pcu["pwr_unit"])         
  line2="  \u251C {0} PKG MAX PWR = {1} W\t\t{2}\n".format( 
           ro, yellow(value), blue("Max power setting allowed in this level") )
  value="{0}".format(tdp_ratio)         
  line3="  \u251C {0} TDP RATIO   = {1}\n".format( ro, yellow(value) )
  value="{0:3.0f}".format(pkg_tdp*pcu["pwr_unit"])         
  line4="  \u2514 {0} PKG TDP     = {1} W\t\t{2}".format(
           ro, yellow(value), blue("Power for this TDP level") )
  return line0+line1+line2+line3+line4


def decode_CONFIG_TDP_LEVEL2(reg):
  comment="Level 2 configurable TDP settings"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,pkg_min_pwr,pkg_max_pwr,_,tdp_ratio,_,pkg_tdp= \
    bitstruct.unpack("b1 u16 u15 u8 u8 b1 u15", reg)
  ro=red("RO")  
  line0="\t\t{0}\n".format(blue(comment))
  value="{0}".format(pkg_min_pwr*pcu["pwr_unit"])         
  line1="  \u251C {0} PKG MIN PWR = {1} W\t\t{2}\n".format(
           ro, yellow(value), 
           blue("Min pkg power setting allowed for this level") )
  value="{0}".format(pkg_max_pwr*pcu["pwr_unit"])         
  line2="  \u251C {0} PKG MAX PWR = {1} W\t\t{2}\n".format( 
           ro, yellow(value), blue("Max power setting allowed in this level") )
  value="{0}".format(tdp_ratio)         
  line3="  \u251C {0} TDP RATIO   = {1}\n".format( ro, yellow(value) )
  value="{0:3.0f}".format(pkg_tdp*pcu["pwr_unit"])         
  line4="  \u2514 {0} PKG TDP     = {1} W\t\t{2}".format(
           ro, yellow(value), blue("Power for this TDP level") )
  return line0+line1+line2+line3+line4


def decode_CONFIG_TDP_NOMINAL_CFG(reg):
  comment="Nominal TDP configuration"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,tdp_ratio= bitstruct.unpack("u24 u8", reg)
  ro=red("RO")  
  value="{0}".format(tdp_ratio)         
  line0="\t\t{0}\n".format(blue(comment))
  line1="  \u2514 {0} TDP RATIO   = {1}\t\t\t{2}".format(
        ro, yellow(value), blue("Pcode set based on SKU and factors in SSKU/softbin and flex impact"))
  return line0+line1


def decode_FLEX_RATIO(reg):
  comment="The Flexible Boot register is written by BIOS in order to modify the maximum "\
          "nonturbo ratio on the next reset. The DP/MP systems use this FLEX_RATIO in this "\
          "register to configure the maximum common boot ratio for all physical processors "\
          "in the system. The value in the FLEX_RATIO take effect on the next reset based on "\
          "the value of FLEX_EN"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,oc_lock,oc_bins,enable,flex_ratio,oc_extra_voltage = \
          bitstruct.unpack("u43 b1 u3 b1 u8 u8", reg)
  ro=red("RO")  
  if oc_lock:
    line1="  \u251C "+ro+" OVERCLOCKING LOCK = " + red("LOCKED") + \
          "\t"+blue("the overclocking bitfields is locked from further writes")+"\n"
  else:
    line1="  \u251C "+ro+" OVERCLOCKING LOCK = " + green("UNLOCKED")+"\n"
  value="{0}".format(oc_bins)
  line2="  \u251C {0} OVERCLOCKING BINS = {1}\t\t{2}\n".format(
        ro, yellow(value), blue("The maximum number of bins by which the part can be overclocked") )
  if enable:
    enable=green("ENABLED")
    comment="FLEX_RATIO will be used to override the max non-turbo ratio on next reboot"
  else:  
    enable=red("DISABLED")
    comment="all writes to FLEX_RATIO will be ignored"
  line0="\t\t"+blued[0]+"\n"+"\n".join(["  \u2502"+"\t"*5+s for s in blued[1:]])+"\n"  
  line3="  \u251C {0} FLEX RATIO is {1}\t\t{2}\n".format(ro, enable, blue(comment))
  value="{0}".format(flex_ratio)
  line4="  \u251C {0} FLEX RATIO        = {1}\t\t{2}\n".format(
        ro, yellow(value), blue("maximum non-turbo ratio <= maximum ratio of hardware"))
  value="{0}".format(oc_extra_voltage/256*1000)
  line5="  \u2514 {0} EXTRA VOLTAGE     = {1} mV\t{2}".format(
        ro, yellow(value), blue("Extra voltage to be used for overclocking"))
  return line0+line1+line2+line3+line4+line5


registers= [
  (0x00, "vendor ID"                , 2, decode_VID_1_30_3_CFG ),
  (0x02, "Device ID"                , 2, "RO 325Ah assigned by each IP/function owner as a unique identifier"),
  (0x04, "PCI Command"              , 2, "mostly hardwired to 0"),
  (0x06, "PCI status"               , 2, ""),
  (0x08, "Rev ID & Class code reg." , 8, ""),
  (0x0C, "CACHE LINE SIZE REGISTER" , 1, "size of cache line"),
  (0x0D, "PCI LATENCY TIMER"        , 1, "Not applicable to PCIe. Hardwired to 0"),
  (0x0E, "HEADER TYPE"              , 1, "PCI header type : multi function device, type 0 header"),
  (0x0F, "BUILT IN SELF TEST"       , 1, "Not supported. Hardwired to 0"),
  (0x2C, "Subsystem vendor ID"      , 2, decode_SVID_1_30_3_CFG),
  (0x2E, "Subsystem ID"             , 2, "Assigned to uniquely identify the subsystem"),
  (0x34, "Capability pointer"       , 1, "Points to the first capability structure : the PCIe capability"),
  (0x3C, "Interrupt line"           , 1, "N/A for PCU"),
  (0x3D, "Interrupt pin"            , 1, "N/A for PCU"),
  (0x3E, "Minimum grant"            , 1, "PCI min grant reg : PCU doesn't burst as a PCI compliant master"),
  (0x3F, "Maximum latency"          , 1, "PCU has no specific requirements for how often it accesses PCI"),
  (0x84, "CAPABILITY REGISTER 0"    , 4, ""),
  (0x88, "CAPABILITY REGISTER 1"    , 4, ""),
  (0x8C, "CAPABILITY REGISTER 2"    , 4, ""),
  (0x90, "CAPABILITY REGISTER 3"    , 4, ""),
  (0x94, "CAPABILITY REGISTER 4"    , 4, ""),
  (0x98, "CAPABILITY REGISTER 5"    , 4, ""),
  (0x9C, "CAPABILITY REGISTER 6"    , 4, ""),
  (0xA0, "CAPABILITY REGISTER 7"    , 4, ""),
  (0xAC, "CAPABILITY REGISTER 8"    , 4, ""),
  (0xB0, "CAPABILITY REGISTER 9"    , 4, ""),
  (0xBC, "CAPABILITY REGISTER 10"   , 4, ""),
  (0xC0, "CONFIG TDP LEVEL1"        , 8, decode_CONFIG_TDP_LEVEL1),
  (0xC8, "CONFIG TDP LEVEL2"        , 8, decode_CONFIG_TDP_LEVEL2),
  (0xDC, "CONFIG TDP NOMINAL"       , 4, decode_CONFIG_TDP_NOMINAL_CFG),
  (0xE0, "FUSED CORES LOW"          , 8, ""),
  (0xE8, "FUSED CORES HIGH"         , 8, ""),
  (0xF0, "FLEX RATIO"               , 8, decode_FLEX_RATIO),
]
