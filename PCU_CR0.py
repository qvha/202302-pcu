#!/usr/bin/python3

import os
import struct
from textwrap import wrap
import bitstruct

from useful_stuff import *
from msr import rdmsr


###################################################################################################
#
#  1. PCU CR0 registers (bus:B31, device:30, function: 0)
#     External Design Specification vol 2 : Registers, §18.1 page 57__
#
###################################################################################################
def decode_VID_1_30_0_CFG(reg):
  comment="assigned by PCI-SIG to Intel"  
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t"+blue(comment)   


def decode_SVID_1_30_0_CFG(reg):
  comment="specifies Intel but can be set to any value once after reset"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t"+blue(comment)   


def decode_PACKAGE_POWER_SKU_CFG(reg):
  if debug:
    a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", reg)
    comment="{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}h ".format( a,b,c,d,e,f,g,h )
  else:      
    comment=""

  comment+="Defines allowed SKU power and timing parameters"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,pgk_max_win_x,pkg_max_win_y,_,pkg_max_pwr,_,pkg_min_pwr,_,pkg_tdp= \
          bitstruct.unpack("u9 u2 u5 b1 u15 b1 u15 b1 u15", reg)
  max_win=(1+pgk_max_win_x/10)*2**pkg_max_win_y


  return "\t\t{0}\n  \u251C PKG_MAX_WIN\t: {1}s\t\t\t{2}\n  \u251C PKG_MAX_PWR\t: {3:4.0f}W\t\t\t{4}\n  \u251C PKG_MIN_PWR\t: {5:4.0f}W\t\t\t{6}\n  \u2514 PKG_TDP\t: {7:4.0f}W\t\t\t{8}".format(
          blue(comment),
          max_win*pcu["time_unit"],    blue("maximal time window allowed for the SKU"),
          pkg_max_pwr*pcu["pwr_unit"], blue("Maximal package power setting allowed for the SKU"),
          pkg_min_pwr*pcu["pwr_unit"], blue("Minimal package power setting for this part"),
          pkg_tdp*pcu["pwr_unit"],     blue("The TPD package power setting allowed for the SKU"))


PRIP_NRG_STTS_CFG_a=0
PRIP_NRG_STTS_CFG_laps=0
def decode_PRIP_NRG_STTS_CFG(reg):
  global PRIP_NRG_STTS_CFG_a
  global PRIP_NRG_STTS_CFG_laps
  comment="Total energy consumed"  
  a=PRIP_NRG_STTS_CFG_a

  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  b=bitstruct.unpack("u32", reg)[0]
  if b==a:
    PRIP_NRG_STTS_CFG_laps+=1   
    return "--- W\t{0}".format(blue(comment))
  if b>a:
    difference=b-a
  else:
    difference=(2**32-1-a)+b  
  deltat=.1*(1+PRIP_NRG_STTS_CFG_laps)
  eps=difference/deltat*pcu["energy_unit"]
  PRIP_NRG_STTS_CFG_a=b
  PRIP_NRG_STTS_CFG_laps=0   
  return "{0:3.0f} W\t{1}".format(eps, blue(comment))
  

def decode_PACKAGE_POWER_SKU_UNIT_CFG(reg):
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,time_unit,_,energy_unit,_,pwr_unit = bitstruct.unpack("u12 u4 u4 u4 u4 u4", reg)
  pcu["time_unit"]=1/2**time_unit
  pcu["energy_unit"]=1/2**energy_unit
  pcu["pwr_unit"]=1/2**pwr_unit
  time_unit  ="{0:.0f}".format(pcu["time_unit"]*1000000)
  energy_unit="{0:.0f}".format(pcu["energy_unit"]*1000000)
  pwr_unit   ="{0:.3f}".format(pcu["pwr_unit"])

  # let's read the MSR_RAPL_POWER_UNIT to compare
  msr=rdmsr(0x606, 4)
  msr=bitstruct.byteswap("{}".format(len(msr)),msr)
  _,msr_time_unit,_,msr_energy_unit,_,msr_pwr_unit = bitstruct.unpack("u12 u4 u4 u4 u4 u4", msr)
  msr_time_unit=1/2**msr_time_unit
  msr_energy_unit=1/2**msr_energy_unit
  msr_pwr_unit=1/2**msr_pwr_unit
  msr_time_unit  ="{0:.0f}".format(msr_time_unit*1000000)
  msr_energy_unit="{0:.0f}".format(msr_energy_unit*1000000)
  msr_pwr_unit   ="{0:.3f}".format(msr_pwr_unit)

  text= "MSR_RAPL_POWER_UNIT\n"

  labels=[ "  \u251C time_unit   ",
           "  \u251C energy_unit ",
           "  \u2514 pwr_unit    " ]

  CSR= [ "{0} \u03BCs | ".format(time_unit).rjust(10),
         "{0} \u03BCJ | ".format(energy_unit).rjust(10),
         "{0} W | ".format(pwr_unit).rjust(10) ]

  MSR= [ "{0} \u03BCs \u2524".format(msr_time_unit).rjust(17),
         "{0} \u03BCJ \u2524".format(msr_energy_unit).rjust(17),
         "{0} W \u2518".format(msr_pwr_unit).rjust(17) ]

  return text + "\n".join([ labels[i] + CSR[i] + MSR[i] for i in range(3) ]) 


PACKAGE_ENERGY_STATUS_CFG_a=0
PACKAGE_ENERGY_STATUS_CFG_laps=0
def decode_PACKAGE_ENERGY_STATUS_CFG(reg):
  global PACKAGE_ENERGY_STATUS_CFG_a
  global PACKAGE_ENERGY_STATUS_CFG_laps
  comment="Package energy consumed by the entire CPU (including IA, Uncore)"
  a=PACKAGE_ENERGY_STATUS_CFG_a

  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  b=bitstruct.unpack("u32", reg)[0]
  if b==a:
    PACKAGE_ENERGY_STATUS_CFG_laps+=1   
    return "--- W\t{0}".format(blue(comment))
  if b>a:
    difference=b-a
  else:
    difference=(2**32-1-a)+b  
  deltat=.1*(1+PACKAGE_ENERGY_STATUS_CFG_laps)
  eps=difference/deltat*pcu["energy_unit"]
  PACKAGE_ENERGY_STATUS_CFG_a=b
  PACKAGE_ENERGY_STATUS_CFG_laps=0   
  return "{0:3.0f} W\t\t{1}".format(eps, blue(comment))


def decode_PLATFORM_ID_CFG(reg):
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,platform_id,_ = bitstruct.unpack("u11 u3 u50", reg)
  if platform_id==0:
    return "1S/2S (shelf 1, 2)"
  elif platform_id==1:
    return "Workstation"  
  elif platform_id==2:
    return "HEDT"
  elif platform_id==4:
    return "DE"
  elif platform_id==7:
    return green("4S/8S (shelf 3, 4)")
  else:
    return "unknown type"


def decode_PLATFORM_INFO_CFG(reg):
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  config_tdp_ext_en,       \
  _,                       \
  _,                       \
  smm_supovr_state_lock_enable, \
  _,                       \
  _,                       \
  _,                       \
  min_operating_ratio,     \
  max_efficiency_ratio,    \
  _,                       \
  asa_enable,              \
  timed_mwait_enable,      \
  _,                       \
  pfat_enable,             \
  config_tdp_levels,       \
  lpm_support,             \
  cpuid_faulting_en,       \
  prg_tj_offset_en,        \
  prg_tdp_lim_en,          \
  prg_turbo_ratio_en,      \
  sample_part,             \
  _,                       \
  ocvolt_ovrd_avail,       \
  ppin_cap,                \
  _,                       \
  _,                       \
  smm_save_cap,            \
  max_non_turbo_lim_ratio, \
  _ =                      \
    bitstruct.unpack("b1 u2 b1 b1 b1 b1 b1 u8 u8 b1 b1 b1 b1 b1 u2 b1 b1 b1 b1 b1 b1 u2 b1 b1 u4 b1 b1 u8 u8", reg)

  flags=["{0}MHz {1}MHz".format( min_operating_ratio*100,
                             max_efficiency_ratio*100) ]

  if config_tdp_levels!=0:         flags.append( "{0:.0f}W".format( 
                                                 max_non_turbo_lim_ratio*pcu["pwr_unit"]) )
  else:                            flags.append( "{}MHz".format(max_non_turbo_lim_ratio*100) )
  if config_tdp_ext_en:            flags.append("TDP_EX")
  if smm_supovr_state_lock_enable: flags.append("SMM_SUPOVR")
  if asa_enable:                   flags.append("ASA")
  if timed_mwait_enable:           flags.append("TimedMWAIT")
  if pfat_enable:                  flags.append("PFAT")
  if   config_tdp_levels==1:       flags.append("TDPx1")
  elif config_tdp_levels==2:       flags.append("TDPx2")
  if lpm_support:                  flags.append("LowPowerMode")
  if cpuid_faulting_en:            flags.append("MISC_FEATURE")
  if prg_tj_offset_en:             flags.append("PRG_TJ")
  if prg_tdp_lim_en:               flags.append("PRG_TDP")
  if prg_turbo_ratio_en:           flags.append("PRG_TURBO")
  if sample_part:                  flags.append("SAMPLE")
  if ocvolt_ovrd_avail:            flags.append("OCVOLT")
  if ppin_cap:                     flags.append("PPIN")
  if smm_save_cap:                 flags.append("SMMsave")
  oneline=" ".join(flags)
  wrapped=wrap(oneline, 60)
  justified=[ "                          " + s for s in wrapped ]
  oneline="\n".join(justified)
  for s in "PRG_TJ", "PRG_TDP", "PRG_TURBO" :
   oneline=oneline.replace(s, green(s) )
  return oneline.lstrip()


def decode_TURBO_ACTIVATION_RATIO_CFG(reg):
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  turbo_activation_ratio_lock,_,max_non_turbo_ratio = bitstruct.unpack("b1 u23 u8", reg)
  if turbo_activation_ratio_lock:
    lock="LOCKED"
  else:
    lock="UNLOCKED"
  if max_non_turbo_ratio==0:
    return "disabled ("+lock+")"
  else:
    return "CPU will treat any P-state request above {} as a request for max turbo".format(max_non_turbo_ratio)


def decode_PACKAGE_TEMPERATURE_CFG(reg):
  if debug:  
    a,b,c,d = struct.unpack("<BBBB", reg)
    comment="{3:02X}{2:02X}{1:02X}{0:02X}h ".format( a, b, c, d )
  else:
    comment=""
  comment+="Package temperature, updated by FW"   
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,temperature = bitstruct.unpack("u24 u8", reg)
  return "{0:3d}°C\t\t{1}".format(temperature, blue(comment))


def decode_PP0_TEMPERATURE_CFG(reg):
  if debug:  
    a,b,c,d = struct.unpack("<BBBB", reg)
    comment="{3:02X}{2:02X}{1:02X}{0:02X}h ".format( a, b, c, d )
  else:
    comment=""
  comment+="PP0 temperature, updated by FW"   
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,temperature = bitstruct.unpack("u24 u8", reg)
  return "{0:3d}°C\t\t{1}".format(temperature, blue(comment))


def decode_P_STATE_LIMTS_CFG(reg):
  comment="maximum IA frequency limit allowed during run-time"   
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  pstt_lock,_,pstt_lim = bitstruct.unpack("b1 u23 u8", reg)
  if pstt_lock:
    lock=red("LOCKED")
  else:
    lock=green("UNLOCKED")
  if pstt_lim==255:  
    return "unlimited ({0:s})\t{1:s}".format( lock, blue(comment) )
  else:
    return "{0}MHz ({1:s})\t{2:s}".format(pstt_lim, lock, blue(comment) )


def decode_PACKAGE_THERM_MARGIN_CFG(reg):
  if debug:  
    a,b,c,d = struct.unpack("<BBBB", reg)
    comment="{3:02X}{2:02X}{1:02X}{0:02X}h ".format( a, b, c, d )
  else:
    comment=""

  comment += "DTS2.0 (Digital Thermal Sensor) negative margin. \n" \
"                                        If the socket is not an MCP, then this parameter\n" \
"                                        represents the margin between the package max temperature\n" \
"                                        to Tcontrol.\n" \
"                                        If the socket is an MCP, then this parameter represents the\n" \
"                                        min temperature margin to the throttling set point temperature\n" \
"                                        among all the dies in the MCP."
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,margin = bitstruct.unpack("u18 s14", reg)
  return "{0} °C\t{1}".format(margin, blue(comment))


def decode_TEMPERATURE_TARGET_CFG(reg):
  if debug:  
    a,b,c,d = struct.unpack("<BBBB", reg)
    hexa = "{3:02X}{2:02X}{1:02X}{0:02X}".format( a, b, c, d )
    line0="{0}h\t".format(blue(hexa))
  else:
    line0="\t\t"
  line0+=blue("Legacy register holding temperature related constants")

  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  lock,_,tj_max_tcc_offset,ref_temp,fan_temp_target_ofst,tcc_offset_clamping_bit,tcc_offset_time_window= \
    bitstruct.unpack("b1 b1 u6 u8 u8 b1 u7", reg)
  if lock:
    lock=red("LOCKED")
  else:
    lock=green("UNLOCKED")

  if tcc_offset_clamping_bit:
    bit=yellow("RATL throttling below P1 is allowed")
  else:  
    bit=yellow("RATL throttling below P1 is not allowed")

  line1=" \u251C TJ_MAX_TCC_OFFSET      : {0}°C ({1}) {2}".format(tj_max_tcc_offset, lock, 
           blue(
             "If allowed and set, the throttle will occur at lower than Tj_max") )
  line2=" \u251C REF_TEMP               : {0}°C\t{1}".format(ref_temp,
           blue(
             "maximum junction temp., Throttle temp., TCC Activation Temp. or Prochot") )
  line3=" \u251C FAN_TEMP_TARGET_OFST   : {0}°C\t\t{1}".format(fan_temp_target_ofst,
           blue(
             "relative offset from the trip temp. at which fans should engage") )
  line4=" \u251C TCC_OFFSET_CLAMPING_BIT: {0} ({1})".format(bit, lock)
  line5=" \u2514 TCC_OFFSET_TIME_WINDOW : {0}s ({1})\t{2}".format(tcc_offset_time_window, lock,
           blue(
             "Describes the RATL averaging time window") )

  return line0+"\n"+line1+"\n"+line2+"\n"+line3+"\n"+line4+"\n"+line5


def decode_PACKAGE_RAPL_LIMIT_CFG(reg):
  comment="The Integrated Graphics driver, CPM driver, BIOS and OS can balance\n" \
"                                        the power budget between the Primary Power Plane (IA) and the\n" \
"                                        Secondary Power Plane (GT) via PRIMARY_PLANE_TURBO_POWER_LIMIT_MSR\n" \
"                                        and SECONDARY_PLANE_TURBO_POWER_LIMIT_MSR"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  lim_lock,_,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,_,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 = \
    bitstruct.unpack("b1 u7 u2 u5 b1 b1 u15 u8 u2 u5 b1 b1 u15", reg)
  if lim_lock:
    lock=red("LOCKED")
  else:
    lock=green("UNLOCKED")

  if clmp_lim_2:
    clamp2=green("can go below P1")
  else:
    clamp2=red("is limited between P0 and P1")

  if clmp_lim_1:
    clamp1=green("can go below P1")
  else:
    clamp1=red("is limited between P0 and P1")

  if lim_2_en:
    pl2enable=red("ENABLED")
  else:
    pl2enable=green("DISABLED")

  if lim_1_en:
    pl1enable=red("ENABLED")
  else:
    pl1enable=green("DISABLED")

  time_window2=(1+lim_2_time_x/10)*2**lim_2_time_y
  time_window1=(1+lim_1_time_x/10)*2**lim_1_time_y
  return "{0}\n" \
  "  PKG_PWR_LIM_2_TIME : {1:7.2f} s\tTime window over which Power_Limit_2 should be maintained\n" \
  "  PKG_PWR_LIM_2      : {2:3.0f} W ({3})\tPPL2/Package Power Limitation 2, always on\n" \
  "  PBM2               : {4}\n" \
  "  PKG_PWR_LIM_1_TIME : {5:7.2f} s\t{6}\n" \
  "  PKG_PWR_LIM_1      : {7:3.0f} W ({8})\t{9}\n" \
  "  PBM1               : {10}".format(lock,time_window2*pcu["time_unit"],
                                            lim_2       *pcu["pwr_unit"], pl2enable, clamp2,
                                            time_window1*pcu["time_unit"], blue("The maximal time window is bounded by PKG_PWR_SKU_MSR[PKG_MAX_WIN]"),
                                            lim_1       *pcu["pwr_unit"], pl1enable, blue("PPL1/Package Power Limitation 1"),
                                            clamp1)


def decode_VR_CURRENT_CONFIG_CFG(reg):
  comment="Limitation on the maximum current consumption of the primary power plane"

  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  psi3_threshold,psi2_threshold,psi1_threshold,lock,current_limit= \
    bitstruct.unpack("p2 u10 u10 u10 b1 p18 u13", reg)
  if lock:
    lock=red("LOCKED")
  else:
    lock=green("UNLOCKED")

  return "{0}\n".format(lock) + format_array( [
    ("PSI3_THRESHOLD", "{0:3d} A".format(psi3_threshold), "Maximum current supported at external voltage regulator PS3" ),
    ("PSI2_THRESHOLD", "{0:3d} A".format(psi2_threshold), "Maximum current supported at external voltage regulator PS2" ),
    ("PSI1_THRESHOLD", "{0:3d} A".format(psi1_threshold), "Maximum current supported at external voltage regulator PS1" ),
    ("CURRENT_LIMIT", "{0:3d} A".format(current_limit//8), "Current limitation")
    ] )


registers= [
  (0x00, "vendor ID"                , 2, decode_VID_1_30_0_CFG ),
  (0x02, "Device ID"                , 2, "RO 3258h assigned by each IP/function owner as a unique identifier"),
  (0x04, "PCI Command"              , 2, "mostly hardwired to 0"),
  (0x06, "PCI status"               , 2, ""),
  (0x08, "Rev ID & Class code reg." , 8, ""),
  (0x0C, "CACHE LINE SIZE REGISTER" , 1, "size of cache line"),
  (0x0D, "PCI LATENCY TIMER"        , 1, "Not applicable to PCIe. Hardwired to 0"),
 (0x0E, "HEADER TYPE"              , 1, "PCI header type : multi function device, type 0 header"),
  (0x0F, "BUILT IN SELF TEST"       , 1, "Not supported. Hardwired to 0"),
  (0x2C, "Subsystem vendor ID"      , 2, decode_SVID_1_30_0_CFG),
  (0x2E, "Subsystem ID"             , 2, "Assigned to uniquely identify the subsystem"),
  (0x34, "Capability pointer"       , 1, "Points to the first capability structure : the PCIe capability"),
  (0x3C, "Interrupt line"           , 1, "N/A for PCU"),
  (0x3D, "Interrupt pin"            , 1, "N/A for PCU"),
  (0x3E, "Minimum grant"            , 1, "PCI min grant reg : PCU doesn't burst as a PCI compliant master"),
  (0x3F, "Maximum latency"          , 1, "PCU has no specific requirements for how often it accesses PCI"),
  (0x80, "PACKAGE POWER SKU"        , 8, decode_PACKAGE_POWER_SKU_CFG),
  (0x88, "PRIMARY PLANE ENERGY STATUS", 4, decode_PRIP_NRG_STTS_CFG),
  (0x8C, "PACKAGE POWER SKU UNIT"   , 4, decode_PACKAGE_POWER_SKU_UNIT_CFG),
  (0x90, "PACKAGE ENERGY STATUS"    , 4, decode_PACKAGE_ENERGY_STATUS_CFG),
  (0xA0, "PLATFORM ID"              , 8, decode_PLATFORM_ID_CFG),
  (0xA8, "PLATFORM INFO"            , 8, decode_PLATFORM_INFO_CFG),
  (0xB0, "TURBO ACTIVATION RATIO"   , 4, decode_TURBO_ACTIVATION_RATIO_CFG),
  (0xB8, "PP0 EFFICIENT CYCLES"     , 4, ""),
  (0xBC, "PP0 THREAD ACTIVITY"      , 4, ""),
  (0xC0, "GPIO Control bits"        , 4, ""),
  (0xC8, "PACKAGE TEMPERATURE"      , 4, decode_PACKAGE_TEMPERATURE_CFG),
  (0xCC, "PP0 TEMPERATURE"          , 4, decode_PP0_TEMPERATURE_CFG),
  (0xD0, "MRC ODT POWER SAVING CFG" , 4, ""),
  (0xD8, "P STATE LIMITS CFG"       , 4, decode_P_STATE_LIMTS_CFG),
  (0xE0, "PACKAGE THERMAL MARGIN"   , 4, decode_PACKAGE_THERM_MARGIN_CFG),
  (0xE4, "TEMPERATURE TARGET"       , 4, decode_TEMPERATURE_TARGET_CFG),
  (0xE8, "PACKAGE RAPL LIMIT CFG"   , 8, decode_PACKAGE_RAPL_LIMIT_CFG),
  (0xF4, "PCU BAR"                  , 4, ""),
  (0xF8, "VR CURRENT CONFIGURATION" , 8, decode_VR_CURRENT_CONFIG_CFG)
]
