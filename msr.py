#!/usr/bin/python3

import os
import sys
import math       # for pow
import struct
import subprocess
import bitstruct
from textwrap import wrap

from useful_stuff import *


def rdmsr(offset, size, core=0):
  """size = size of data to read, in Byte
  offset = equivalent to the msr number
  core = each core has its own set of msr
  """

  msrfile="/dev/cpu/{0:d}/msr".format(core)
  with open(msrfile, "rb") as fd:
    fd.seek(offset)
    return fd.read(size)


def wrmsr(offset, databytes, core=0):
  msrfile="/dev/cpu/{0:d}/msr".format(core)
  try:
    with open(msrfile, "r+b") as fd:           # w+ erases, then opens. r+ opens for reading and writing
      fd.seek(offset)
      n=fd.write(databytes)
  except:
    #sys.exit("wrmsr {0:04X}h : Could not write {1} into {2}\n".format( 
    #  offset, databytes.hex(), msrfile ))
    print("wrmsr {0:X}h : Could not write {1} into {2}\n".format( 
      offset, databytes.hex(), msrfile ))

  return n


def count_cores():
  """return the number of cores, by counting folders in /sys/class/msr"""
  dirarray=os.listdir("/sys/class/msr/")  # contains [ "msr23", "msr24", ...]
  return len(dirarray)


def read_mailbox(offset, size, core=0):
  msrfile="/dev/cpu/{0:d}/msr".format(core)
  with open(msrfile, "rb") as fd:
    # we poll on the last bit
    count=0
    while count<20:
      fd.seek(offset+size-1)
      chunk=fd.read(1)
      if int.from_bytes(chunk, "little", signed=False)>>7 : time.sleep(.1)
      else: break
      count+=1
    if count>=20:
      raise Exception("mailbox still BUSY")
    fd.seek(offset)
    return fd.read(size)


def write_mailbox(offset, size, data, core=0):
  msrfile="/dev/cpu/{0:d}/msr".format(core)
  with open(msrfile, "r+b") as fd:             # w+ erases, then opens. r+ opens for reading and writing
    # we poll on the last bit
    count=0
    while count<20:
      fd.seek(offset+size-1)
      chunk=fd.read(1)
      if int.from_bytes(chunk, "little", signed=False)>>7 : time.sleep(.1)
      else: break
      count+=1
    if count>=20:
      raise Exception("mailbox still BUSY")
    fd.seek(offset)
    return fd.write(data)


##### MSR 65Ch PLATFORM_POWER_LIMIT_SRVR ##########################################################
def read_PLATFORM_POWER_LIMIT_SRVR():
  # Platform power limit
  rd_chunk=rdmsr(0x65C, 8)   # only ready CPU0
  swapped=bitstruct.byteswap("8",rd_chunk)
  lock,power_limit2_time,critical_power_clamp2,power_limit2_en, power_limit2,\
       power_limit1_time,critical_power_clamp1,power_limit1_en, power_limit1 = \
    bitstruct.unpack("b1 p5 u7 b1 b1 u5 p6 u7 b1 b1 u17", swapped)

  if lock:
    lock=red("LOCKED")  
  else:
    lock=green("UNLOCKED")
  
  if critical_power_clamp2:
    critical_power_clamp2=yellow("NOT ENFORCED")
  else:
    critical_power_clamp2=yellow("ENFORCED")

  if critical_power_clamp1:
    critical_power_clamp1=yellow("NOT ENFORCED")
  else:
    critical_power_clamp1=yellow("ENFORCED")

  if power_limit2_en:
    power_limit2_en=yellow("NOT ENFORCED")
  else:
    power_limit2_en=yellow("ENFORCED")

  if power_limit1_en:
    power_limit1_en=yellow("NOT ENFORCED")
  else:
    power_limit1_en=yellow("ENFORCED")

  power_limit2=yellow( "{0:.0f}".format(power_limit2 /8)) 
  yypower_limit1=yellow( "{0:.0f}".format(power_limit1 /8)) 
  
  print( "read_PLATFORM_POWER_LIMIT_SRVR = {0:016X}h".format(int.from_bytes(rd_chunk,"little",signed=False)),
         lock )
  print( "\t         POWER_LIMIT1 = {0} W\t\t\t         POWER_LIMIT2 = {1} W".format(power_limit1,
                                                                                   power_limit2 ) ) 
  print( "\tCRITICAL_POWER_CLAMP1 = {0}\t\tCRITICAL_POWER_CLAMP2 = {1}".format(critical_power_clamp1,
                                                                               critical_power_clamp2 ) ) 
  print( "\t  POWER_LIMIT1_ENABLE = {0}\t\t  POWER_LIMIT2 ENABLE = {1}".format(power_limit1_en,
                                                                               power_limit2_en) ) 


##### MSR 601h  VR CURRENT CONFIG #################################################################
def read_VR_CURRENT_CONFIG(core=0):
  # Power Limit 4 (PL4).
  # Package-level maximum power limit (in Watts)
  # It is a proactive, instantaneous limit.
  rd_chunk=rdmsr(0x601, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  lock,current_limit = bitstruct.unpack("p32 b1 p18 u13", swapped)

  if lock:
    lock=red("LOCKED")  
  else:
    lock=green("UNLOCKED")
 
  current_limit=yellow( "{0:.0f}".format(current_limit / 8 )) 
 
  print( "read_VR_CURRENT_CONFIG 601h = {0:016X}h".format(int.from_bytes(rd_chunk,"little",signed=False)),
         lock )
  print( "\t\tCURRENT LIMIT = {0} A".format(current_limit))


def write_VR_CURRENT_CONFIG(current_limit, core=0):
  """current_limit : in unit A"""
  swapped=bitstruct.pack("p32 b1 p18 u13", False, current_limit * 8 )
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x601, wr_chunk, core)


##### MSR 603h  VR MISC CONFIG ###################################################################
""" INTEL 613938 Eagle Stream Bios writer's Guide 
  format 3.13 is a fixed point format where the decimal point is assumed to be 3 digits from the left.
  dividing the whole number by 2^13 gives the corresponding number value in integer format.
  let 110000110010011 be the 3.13 representation of a float.
  (110000110010011)2 = (49699)10
  49699 / 2^13 = 6.0667724609375
  060667724609375 is the integer format equivalent of 110000110010011 in 3.13 format"""


def read_VR_MISC_CONFIG(core=0):
  # Input voltage regulator configuration parameters
  rd_chunk=rdmsr(0x603, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,iout_offset,min_vid, \
  leak_load_line_r,idle_load_line_r,dynamic_load_line_r = bitstruct.unpack(
          "p11 b1 b1 b1 u10 s8 u8 u8 u8 u8", swapped)

  # IOUT_SLOPE is a scalar applied to dIout before it is consumed by the CPU
  # it represents a 1.x number in u10.1.9 format (0.0 to 2.0)
  iout_slope=iout_slope/math.pow(2,9)

  # Iout_offset is a factor applied to I coming out of the VRs, encoded in 3.11, in 8 bits
  # they say, its maximum is 6,25% and minimum is -6,25%
  # 0,0049 en 2^11 devient : 10.0352
  # 0.0625 en 2^11 devient : 128.0
  iout_offset=iout_offset/math.pow(2,11)

  return print("read_VR_MISC_CONFIG[{0}]={1},{2},{3},{4},{5:.5f},{6},{7},{8},{9}".format(core,
      idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,iout_offset,min_vid, \
      leak_load_line_r,idle_load_line_r,dynamic_load_line_r ) ), \
      idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,iout_offset,min_vid, \
      leak_load_line_r,idle_load_line_r,dynamic_load_line_r


def write_VR_MISC_CONFIG(idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,
                         iout_offset,min_vid, leak_load_line_r,idle_load_line_r,dynamic_load_line_r, core=0):
  # encode iout_slope
  iout_slope=math.floor(iout_slope*math.pow(2,9))

  """iout_offset : a factor of Iccmax at the VR"""
  # encode iout_offset as x.11 integer
  iout_offset=math.floor(iout_offset*math.pow(2,11))

  swapped=bitstruct.pack("p11 b1 b1 b1 u10 s8 u8 u8 u8 u8",idle_entry_decay_enable,idle_entry_ramp_rate,idle_exit_ramp_rate,iout_slope,
                         iout_offset,min_vid, leak_load_line_r,idle_load_line_r,dynamic_load_line_r)
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x603, wr_chunk, core)


##### MSR 194h  FLEX RATIO ########################################################################
def read_FLEX_RATIO(core=0):
  # I used info from 18.4.34 PCI FLEX_RATIO_CFG
  comment="The Flexible Boot register is written by BIOS in order to modify the maximum "\
          "nonturbo ratio on the next reset. The DP/MP systems use this FLEX_RATIO in "\
          "this register to configure the maximum common boot ratio for all physical "\
          "processors in the system. The value in the FLEX_RATIO take effect on the next "\
          "reset based on the value of FLEX_EN."
  rd_chunk=rdmsr(0x194, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  oc_lock,oc_bins,enable,flex_ratio,oc_extra_voltage = \
    bitstruct.unpack("p43 b1 u3 b1 u8 u8", swapped)

  result=[ oc_lock,oc_bins,enable,flex_ratio,oc_extra_voltage ]

  if oc_lock:
    oc_lock=red("LOCKED")  
  else:
    oc_lock=green("UNLOCKED")

  if enable:
    enable=green("YES, on the next reboot")  
  else:
    enable=red("NO")

  oc_extra_voltage=yellow( "{0:.0f}".format(oc_extra_voltage  / 256 * 1000 )) 
  flex_ratio=yellow( "{}".format(flex_ratio )) 
  
  print( "read_FLEX_RATIO[{0}] 194h = {1:016X}h".format(
         core, int.from_bytes(rd_chunk,"little",signed=False)),
         oc_lock )
  print( "\t\tOC BINS          = {}".format(oc_bins))
  print( "\t\tFLEX RATIO       = {0} {1}".format( flex_ratio, enable) )
  print( "\t\tOC EXTRA VOLTAGE = {0} mV".format(oc_extra_voltage))

  # careful, oc_extra_voltage has no conversion done to it
  return result


  # careful, oc_extra_voltage has no conversion done to it
def write_FLEX_RATIO(oc_lock,oc_bins,enable,flex_ratio,oc_extra_voltage, core=0):
#  oc_lock=True
#  oc_bins=7
#  enable=False
  swapped=bitstruct.pack("p43 b1 u3 b1 u8 u8",
                          oc_lock,oc_bins,enable,flex_ratio,oc_extra_voltage )
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x194, wr_chunk, core)

    
##### MSR 1A2h TEMPERATURE TARGET #################################################################
def read_TEMPERATURE_TARGET(core=0):
  # I used info from 20.143 TEMPERATURE_TARGET
  comment="Legacy register holding temperature related constants for Platform use."
  rd_chunk=rdmsr(0x1A2, 4, core)
  swapped=bitstruct.byteswap("4",rd_chunk)
  locked,tj_max_tcc_offset,ref_temp,temperature,tcc_offset_clamping_bit,tcc_offset_time_window = \
    bitstruct.unpack("b1 p1 u6 u8 u8 b1 u7", swapped)

  result=[ locked,tj_max_tcc_offset,ref_temp,temperature,
           tcc_offset_clamping_bit,tcc_offset_time_window ]

  if locked:
    locked=red("LOCKED")  
  else:
    locked=green("UNLOCKED")

  print( "read_TEMPERATURE_TARGET[{0}] 1A2h = {1:016X}h".format(
         core, int.from_bytes(rd_chunk,"little",signed=False)),
         locked )

  print( format_array( [ 
                        ("Tj max Tcc offset","{0:>2d} °C".format(tj_max_tcc_offset),"Temperature offset from the TJ Max. "
     "Used for throttling temperature. Will not impact temperature reading. If offset is allowed "
     "and set - the throttle will occur and reported at lower then Tj_max."),                     
                        ("Ref Temp", "{0:>2d} °C".format(ref_temp), "Maximum junction temperature, "
     "also referred to as the Throttle Temperature, TCC Activation Temperature or Prochot "
     "Temperature. This is the temperature at which the Adaptive Thermal Monitor is activated." ),
                        ("Fan Temperature target offset", "{0:>2d} °C".format(temperature), "Fan Temperature Target Offset "
     "(a.k.a. T-Control) indicates the relative offset from the Thermal Monitor Trip Temperature "
     "at which fans should be engaged" ),
                        ("Tcc offset clamping bit", "{}".format(tcc_offset_clamping_bit), "when enabled will allow RATL throttling below P1"),
                        ("tcc_offset_time_window", "{0:>2d} s".format(tcc_offset_time_window), "Describes the RATL averaging time window") ] )
  )      
  return result


##### MSR 1ADh TURBO RATIO LIMIT ##################################################################
def read_TURBO_RATIO_LIMIT(core=0):
  comment="This MSR indicates the factory configured values for active core ranges (1-8) and not "\
          "active cores. Each field in MSR_TURBO_RATIO_LIMIT_CORES (MSR 1AEh) denotes "\
          "the active core count. "\
          "Software can configure these limits when PRG_TURBO_RATIO (msr CEh[28])==1. "\
          "Instead of specifying a ratio for each active core count (legacy behavior), active core "\
          "counts with an identical turbo ratio limit belong to a single active core range that act "\
          "as a turbo limit for that entire range of active cores"
  rd_chunk=rdmsr(0x1AD, 8, core)
  ratio1,ratio2,ratio3,ratio4,range1,range2,range3,range4 = struct.unpack("BBBBBBBB", rd_chunk)

  print( "read_TURBO_RATIO_LIMIT[{0}] 1ADh = {1:08X}h".format(
         core, int.from_bytes(rd_chunk,"little",signed=False))
         )
  print( "\t\tRATIO1 = {0}\t\tRANGE1 = {1}".format(ratio1,range1))
  print( "\t\tRATIO2 = {0}\t\tRANGE2 = {1}".format(ratio2,range2))
  print( "\t\tRATIO3 = {0}\t\tRANGE3 = {1}".format(ratio3,range3))
  print( "\t\tRATIO4 = {0}\t\tRANGE4 = {1}".format(ratio4,range4))


##### MSR 1FCh POWER CTL ##########################################################################
def read_POWER_CTL(core=0):
  rd_chunk=rdmsr(0x1FC, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  pch_neg_disable, ltr_iio_disable, pwr_perf_tuning_cfg_mode, pwr_perf_tuning_enable_dyn_switching, \
  pwr_perf_tuning_disable_sapm_ctrl, therm_rsvd_en, cstate_prewake_disable, disable_autonomous, \
  disable_ook, disable_sa_optimization, disable_ring_ee, vr_therm_alert_disable, prochot_lock, \
  prochot_response, dis_prochot_out, rth_disable, ee_turbo_disable, pwr_perf_platfrm_ovr, \
  phold_sr_disable, phold_cst_prevention_init, fast_brk_int_en, fast_brk_snp_en, \
  sapm_imc_c2_policy, c1e_enable, enable_bidir_prochot = bitstruct.unpack(
          "p27 b1b1b1b1b1b1b1 p1 b1b1b1b1b1b1b1b1b1b1b1b1 u11 p1"+"b1"*5, swapped)
  flags=[]
  if pch_neg_disable: flags.append(  red("PCH_NEG"))
  else:               flags.append(green("PCH_NEG"))

  if ltr_iio_disable: flags.append(  red("LTR_IIO"))
  else:               flags.append(green("LTR_IIO"))

  if pwr_perf_tuning_cfg_mode: flags.append("PWR_PERF_TUNING")

  if not vr_therm_alert_disable:  flags.append("VR_THERM_ALERT")

  if prochot_lock: flags.append(  red("PROCHOT_LOCKED"))
  else:            flags.append(green("PROCHOT_UNLOCKED"))
  
  print(" ".join(flags))


def write_POWER_CTL(VR_THERM_ALERT_DISABLE, core=0):
  rd_chunk=rdmsr(0x1FC, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  pch_neg_disable, ltr_iio_disable, pwr_perf_tuning_cfg_mode, pwr_perf_tuning_enable_dyn_switching, \
  pwr_perf_tuning_disable_sapm_ctrl, therm_rsvd_en, cstate_prewake_disable, disable_autonomous, \
  disable_ook, disable_sa_optimization, disable_ring_ee, vr_therm_alert_disable, prochot_lock, \
  prochot_response, dis_prochot_out, rth_disable, ee_turbo_disable, pwr_perf_platfrm_ovr, \
  phold_sr_disable, phold_cst_prevention_init, fast_brk_int_en, fast_brk_snp_en, \
  sapm_imc_c2_policy, c1e_enable, enable_bidir_prochot = bitstruct.unpack(
          "p27 b1b1b1b1b1b1b1 p1 b1b1b1b1b1b1b1b1b1b1b1b1 u11 p1"+"b1"*5, swapped)

  swapped=bitstruct.pack("p27 b1b1b1b1b1b1b1 p1 b1b1b1b1b1b1b1b1b1b1b1b1 u11 p1"+"b1"*5, 
    pch_neg_disable, ltr_iio_disable, pwr_perf_tuning_cfg_mode, pwr_perf_tuning_enable_dyn_switching,
    pwr_perf_tuning_disable_sapm_ctrl, therm_rsvd_en, cstate_prewake_disable, disable_autonomous,
    disable_ook, disable_sa_optimization, disable_ring_ee, VR_THERM_ALERT_DISABLE, prochot_lock,
    prochot_response, dis_prochot_out, rth_disable, ee_turbo_disable, pwr_perf_platfrm_ovr,
    phold_sr_disable, phold_cst_prevention_init, fast_brk_int_en, fast_brk_snp_en,
    sapm_imc_c2_policy, c1e_enable, enable_bidir_prochot)

  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x1FC, wr_chunk, core)
    

##### MSR 2A0h PRMRR BASE 0 #######################################################################
def read_PRMRR_BASE_0(core=0):
  rd_chunk=rdmsr(0x2A0, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A1h PRMRR BASE 1 #######################################################################
def read_PRMRR_BASE_1(core=0):
  rd_chunk=rdmsr(0x2A1, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A2h PRMRR BASE 2 #######################################################################
def read_PRMRR_BASE_2(core=0):
  rd_chunk=rdmsr(0x2A2, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A3h PRMRR BASE 3 #######################################################################
def read_PRMRR_BASE_3(core=0):
  rd_chunk=rdmsr(0x2A3, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A4h PRMRR BASE 4 #######################################################################
def read_PRMRR_BASE_4(core=0):
  rd_chunk=rdmsr(0x2A4, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A5h PRMRR BASE 5 #######################################################################
def read_PRMRR_BASE_5(core=0):
  rd_chunk=rdmsr(0x2A5, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A6h PRMRR BASE 6 #######################################################################
def read_PRMRR_BASE_6(core=0):
  rd_chunk=rdmsr(0x2A6, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


##### MSR 2A7h PRMRR BASE 7 #######################################################################
def read_PRMRR_BASE_7(core=0):
  rd_chunk=rdmsr(0x2A7, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  base,configured,memtype = bitstruct.unpack(
          "p12 u40 p8 b1 u3", swapped)

  return base,configured,memtype


def read_PRMRR_BASE(prmrr=0, core=0):
  if prmrr==0:
    return read_PRMRR_BASE_0(core)
  elif prmrr==1:
    return read_PRMRR_BASE_1(core)
  elif prmrr==2:
    return read_PRMRR_BASE_2(core)
  elif prmrr==3:
    return read_PRMRR_BASE_3(core)
  elif prmrr==4:
    return read_PRMRR_BASE_4(core)
  elif prmrr==5:
    return read_PRMRR_BASE_5(core)
  elif prmrr==6:
    return read_PRMRR_BASE_6(core)
  elif prmrr==7:
    return read_PRMRR_BASE_7(core)
  else:
    sys.stderr.write("coding error : prmrr cannot exceed 7\n")
    sys.exit(1)

     
##### MSR CEh PLATFORM_INFO #######################################################################
def read_PLATFORM_INFO(core=0):
  comment="This register contains read_only package level ratio information"
  rd_chunk=rdmsr(0xCE, 8, core)
  swapped=bitstruct.byteswap("8",rd_chunk)
  smm_supovr_state,optane_2lm,edram,min_operating_ratio,max_efficiency_ratio,asa,timed_mwait,\
  peg2dmidis,bios_guard,config_tdp_levels,lpm,cpuid_faulting,prg_tj_offset,prg_tdp_lim,\
  prg_turbo_ratio,sample,fivr_rfi_tuning,ocvolt_ovrd,ppin,rar,smm_save_cap,\
  max_non_turbo_lim_ratio= \
    bitstruct.unpack("p4 b1 b1 b1 p1 u8 u8 p1 b1 b1 b1 b1 u2 b1 b1 b1 b1 b1 b1 p1 b1 b1 b1 p5 b1 b1 u8 p8", swapped)

  flags=[]

  if smm_supovr_state: flags.append(highlight("SMM_SUPOVR_STATE"))
  else:                flags.append(          "SMM_SUPOVR_STATE" )

  if optane_2lm: flags.append(highlight("OPTANE_2LM"))
  else:          flags.append(          "OPTANE_2LM" )

  if edram: flags.append(highlight("EDRAM"))
  else:     flags.append(          "EDRAM" )

  if smm_supovr_state: flags.append(highlight("SMM_SUPOVR_STATE"))
  else:                flags.append(          "SMM_SUPOVR_STATE" )

  min_operating_ratio =yellow("{}".format( min_operating_ratio*100))
  max_efficiency_ratio=yellow("{}".format(max_efficiency_ratio*100))
  
  if asa: flags.append(highlight("ASA"))
  else:   flags.append(          "ASA" )

  if timed_mwait: flags.append(highlight("TIMED_MWAIT"))
  else:           flags.append(          "TIMED_MWAIT" )

  if peg2dmidis: flags.append(highlight("PEG2MIDIS"))
  else:          flags.append(          "PEG2MIDIS" )

  if bios_guard: flags.append(highlight("BIOS_GUARD"))
  else:          flags.append(          "BIOS_GUARD" )

  if config_tdp_levels: flags.append(highlight("CONFIG_TDP"))
  else:                 flags.append(          "CONFIG_TDP" )

  if lpm: flags.append(highlight("LPM"))
  else:   flags.append(          "LPM" )

  if cpuid_faulting: flags.append(highlight("CPUID_FAULTING"))
  else:              flags.append(          "CPUID_FAULTING" )

  if prg_tj_offset: flags.append(highlight("PRG_TJ_OFFSET"))
  else:             flags.append(          "PRG_TJ_OFFSET" )

  if prg_tdp_lim: flags.append(highlight("PRG_TDP_LIM"))
  else:           flags.append(          "PRG_TDP_LIM" )

  if prg_turbo_ratio: flags.append(highlight("PRG_TURBO_RATIO"))
  else:               flags.append(          "PRG_TURBO_RATIO" )

  if sample: flags.append(highlight("SAMPLE"))
  else:      flags.append(          "SAMPLE" )

  if fivr_rfi_tuning: flags.append(highlight("FIVR_RFI_TUNING"))
  else:               flags.append(          "FIVR_RFI_TUNING" )

  if ocvolt_ovrd: flags.append(green("OCVOLT_OVRD"))
  else:           flags.append(          "OCVOLT_OVRD" )

  if ppin: flags.append(highlight("PPIN"))
  else:    flags.append(          "PPIN" )

  if rar: flags.append(highlight("RAR"))
  else:   flags.append(          "RAR" )

  if smm_save_cap: flags.append(highlight("SMM_SAVE_CAP"))
  else:            flags.append(          "SMM_SAVE_CAP" )

  max_non_turbo_lim_ratio=yellow("{}".format(max_non_turbo_lim_ratio*100))

  print( "read_PLATFORM_INFO[{0}] 0CEh = {1:08X}h".format(
         core, int.from_bytes(rd_chunk,"little",signed=False))
         )
  print( "\t\tMIN_OPERATING_RATIO    = {0} MHz".format(min_operating_ratio))
  print( "\t\tMAX_EFFICIENCY_RATIO   = {0} MHz".format(max_efficiency_ratio))
  print( "\t\tMAX_NON_TURBO_LIM_RATIO= {0} MHz".format(max_non_turbo_lim_ratio))
  print( " ".join(flags))


##### MSR 610h PACKAGE_RAPL_LIMIT_CFG #############################################################
def read_PACKAGE_RAPL_LIMIT_CFG(core=0):
  comment="The Integrated Graphics driver, CPM driver, BIOS and OS can balance\n" \
"                                        the power budget between the Primary Power Plane (IA) and the\n" \
"                                        Secondary Power Plane (GT) via PRIMARY_PLANE_TURBO_POWER_LIMIT_MSR\n" \
"                                        and SECONDARY_PLANE_TURBO_POWER_LIMIT_MSR"
  rd_chunk=rdmsr(0x610, 8, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  lim_lock,_,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,_,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 = \
    bitstruct.unpack("b1 u7 u2 u5 b1 b1 u15 u8 u2 u5 b1 b1 u15", swapped)
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
  print( "read_PACKAGE_RAPL_LIMIT_CFG[{0}] 610h = {1:016X}h".format(
         core, int.from_bytes(rd_chunk,"little",signed=False)))
  return "{0}\n" \
  "  PKG_PWR_LIM_2_TIME : {1:7.0f} s\t\tTime window over which Power_Limit_2 should be maintained\n" \
  "  PKG_PWR_LIM_2      : {2:3.0f} W ({3})\tPPL2/Package Power Limitation 2, always on\n" \
  "  PBM2               : {4}\n" \
  "  PKG_PWR_LIM_1_TIME : {5:7.1f} ms\t\tThe maximal time window is bounded by PKG_PWR_SKU_MSR[PKG_MAX_WIN]\n" \
  "  PKG_PWR_LIM_1      : {6:3.0f} W ({7})\tPPL1/Package Power Limitation 1\n" \
  "  PBM1               : {8}".format(lock,time_window2*pcu["time_unit"],
                                           lim_2       *pcu["pwr_unit"], pl2enable, clamp2,
                                           time_window1*pcu["time_unit"]*1000,
                                           lim_1       *pcu["pwr_unit"], pl1enable, clamp1)


def write_PACKAGE_RAPL_LIMIT_CFG(lim_1_time_x, lim_1_time_y, lim_1,
                                 lim_2_time_x, lim_2_time_y, lim_2, core=0):
  """lim_1, lim_2 : TDP (W)
ppl1_time, ppl2_time : tau (?), time window (ms)"""

  # local constants
  lim_lock=False  # When set, all settings in this register are locked and are treated as Read Only.
  lim_1_en=True   # Because the cpu must maintain the power consumption to TDP, lim_1_en is always True
  lim_2_en=True   # The Package PL2 is always enabled. Writing a 0 to the bit will have no effect.
  clmp_lim_1=True # This bit is writable only when CPUID.(EAX=6):EAX[4] is set
  clmp_lim_2=True # This bit is writable only when CPUID.(EAX=6):EAX[4] is set

  swapped=bitstruct.pack("b1 p7 u2 u5 b1 b1 u15 p8 u2 u5 b1 b1 u15", 
                          lim_lock,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 )
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x610, wr_chunk, core)

    
##### MSR 611h PACKAGE ENERGY STATUS ########################################################
def read_PACKAGE_ENERGY_TIME_STATUS(core=0):
  """Package energy consumed by the entire CPU (including IA, GT, and uncore).
  Expressed in unit = PACKAGE_POWER_SKU[ ENERGY_UNIT ] ( 61 uJ )
  """

  rd_chunk=rdmsr(0x611, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  total_energy_consumed= bitstruct.unpack("u32", swapped)

  return total_energy_consumed * pcu[ "energy_unit" ]
  

##### MSR 612h PACKAGE ENERGY TIME STATUS ###################################################
def read_PACKAGE_ENERGY_TIME_STATUS(core=0):
  """Package energy consumed by the entire CPU (including IA, GT, and uncore).
  Expressed in unit = PACKAGE_POWER_SKU[ ENERGY_UNIT ] ( 61 uJ )
  [ returns elapsed time, and energy consumed. For an accurate divide ]
  """

  rd_chunk=rdmsr(0x612, 8, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
#  total_time_elapsed, total_energy_consumed= bitstruct.unpack("u32 u32", swapped)
  total_time_elapsed, high, low= bitstruct.unpack("u32 u18 u14", swapped)

  u18_14=high + low * pcu[ "energy_unit" ] 
  return total_time_elapsed    * pcu[   "time_unit" ], \
         u18_14 
#         total_energy_consumed * pcu[ "energy_unit" ]
  

def write_PACKAGE_ENERGY_TIME_STATUS(elapsed_time, consumed_energy, core=0):
  # i skipped the unit conversion, because i only intent to write 0  
  swapped=bitstruct.pack("u32 u32", elapsed_time, consumed_energy)
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x612, wr_chunk, core)


##### MSR 613h PACKAGE RAPL PERF STATUS #####################################################
def read_PACKAGE_RAPL_PERF_STATUS(core=0):
  """counts time spent in lower than requested P-state, due to power constraint. unknown unit.
  guessing pcu[ "time_unit" ] but using text :
  resolution of 1/1024 s  
  """

  rd_chunk=rdmsr(0x613, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  count= bitstruct.unpack("u32", swapped)[0]

  return count * 1024
  

##### MSR 614h PACKAGE_POWER_SKU ############################################################
def read_PACKAGE_POWER_SKU(core=0):
  rd_chunk=rdmsr(0x614, 8, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  pkg_max_win_x, pkg_max_win_y,pkg_max_pwr, pkg_min_pwr, pkg_tdp= \
    bitstruct.unpack("p9 u2 u5 p1 u15 p1 u15 p1 u15", swapped)
  pkg_max_win = (1+pkg_max_win_x/10)*2**pkg_max_win_y

  return """maximal time window = {0:3.2f} ms    maximal package power = {1:3.0f}W
TDP package power   = {3:3.0f}W       minimal package power = {2:3.0f}W""".format(
                                  pkg_max_win * pcu[ "time_unit" ] * 1000,
                                  pkg_min_pwr * pcu[ "pwr_unit" ],
                                  pkg_max_pwr * pcu[ "pwr_unit" ],
                                  pkg_tdp     * pcu[ "pwr_unit" ])
  

##### MSR 619h DRAM ENERGY STATUS ###########################################################
def read_DRAM_ENERGY_STATUS(core=0):
  """Accumulates the consumed energy by the DIMMs (summed across all channels)
  format 18.14, resolution 61uJ, 0 to 2.62e5J
  """

  rd_chunk=rdmsr(0x619, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  high, low= bitstruct.unpack("u18 u14", swapped)
  # Old school u18.14 fixed-point fractional representation
  # the fractional part on 14 bits, corresponds to the energy unit, defined as 1/2^14 in Joule.
  # they are 2^14 buckets of 61uJ each, totalizing 1J when all buckets are used.
  # the integer part, because of the maximum in the text, is directly the value in Joule
  # as 2^18 = 262144, whch is the max. Therefore, the formula is :
  consumed_energy = high + low * pcu[ "energy_unit" ] # in Joule

  return consumed_energy
  

##### MSR 639h PRIMARY PLANE ENERGY STATUS ###########################################################
def read_PRIMARY_PLANE_ENERGY_STATUS(core=0):
  """Reports total energy consumed. The counter will wrap around and continue counting
  when it reaches its limit.
  unit is PACKAGE_POWER_SKU_UNIT[ENERGY_UNIT]
  updated every 1ms
  """

  rd_chunk=rdmsr(0x639, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  energy_value= bitstruct.unpack("u32", swapped)[0]

  return energy_value * pcu[ "energy_unit" ] # in Joule
  

##### MSR 1A0h IA32_MISC_ENABLE #############################################################
def read_IA32_MISC_ENABLE(core=0):
  rd_chunk=rdmsr(0x1A0, 8, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  turbo_mode, tpr_message, limit_cpuid_maxval,monitor_fsm,enhanced_speedstep,pebs,bts,perfmon,\
  tcc, fast_strings= \
    bitstruct.unpack("p25 b1 p14 b1 b1 p3 b1 p1 b1 p3 b1 b1 p3 b1 p3 b1 p2 b1", swapped)
  flags=[]  
  if turbo_mode: flags.append(          "[TURBO]" )
  else:          flags.append(highlight("[TURBO]"))

  if tpr_message: flags.append(          "[TPR]" )
  else:           flags.append(highlight("[TPR]"))

  if limit_cpuid_maxval: flags.append(highlight("[LIMIT_MAX_CPUID]"))
  else:                  flags.append(          "[LIMIT_MAX_CPUID]" )

  if monitor_fsm: flags.append(highlight("[MONITOR_FSM]"))
  else:           flags.append(          "[MONITOR_FSM]" )

  if enhanced_speedstep: flags.append(highlight("[ENHANCED_SPEEDSTEP]"))
  else:                  flags.append(          "[ENHANCED_SPEEDSTEP]" )

  if pebs: flags.append(          "[PEBS]" )
  else:    flags.append(highlight("[PEBS]"))

  if bts: flags.append(          "[BTS]" )
  else:   flags.append(highlight("[BTS]"))

  if perfmon: flags.append(highlight("[PERFMON]"))
  else:       flags.append(          "[PERFMON]" )

  if tcc: flags.append(highlight("[TCC]"))
  else:   flags.append(          "[TCC]" )

  if fast_strings: flags.append(highlight("[FAST_STRINGS]"))
  else:            flags.append(          "[FAST_STRINGS]" )

  oneline=" ".join(flags)
  wrapped=wrap(oneline, 80)
  for i in range(1,len(wrapped)):
      wrapped[i]='\t'*7+wrapped[i]
  print( "read_IA32_MISC_ENABLE[{0}] 1A0h = {1:016X}h\t{2}".format(
             core, int.from_bytes(rd_chunk,"little",signed=False),
             "\n".join(wrapped)
             )
       )

  return turbo_mode, tpr_message, limit_cpuid_maxval,monitor_fsm,enhanced_speedstep,pebs,bts,perfmon,\
  tcc, fast_strings


# testé, la fonction marche
def write_IA32_MISC_ENABLE(turbo_mode, tpr_message, limit_cpuid_maxval, monitor_fsm, enhanced_speedstep,\
                           pebs,bts,perfmon, tcc, fast_strings, core=0):
  swapped=bitstruct.pack("p25 b1 p14 b1 b1 p3 b1 p1 b1 p3 b1 b1 p3 b1 p3 b1 p2 b1",
                         turbo_mode, tpr_message, limit_cpuid_maxval,monitor_fsm,enhanced_speedstep,\
                         pebs,bts,perfmon, False, fast_strings)
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x1A0, wr_chunk, core)


##### MSR 64Ch TURBO ACTIVATION RATIO (TAR) #################################################
def read_TURBO_ACTIVATION_RATIO(core=0):
  rd_chunk=rdmsr(0x64C, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  tar_lock,max_tar= bitstruct.unpack("b1 p23 u8", swapped)

  if tar_lock: tar_lock=red("LOCKED")
  else:        tar_lock=green("UNLOCKED")

  max_tar=yellow("{}".format(max_tar*100))

  print( "read_TURBO_ACTIVATION_RATIO[{0}] 64Ch = {1:016X}h\t max_tar={2} MHz {3}".format(
             core, 
             int.from_bytes(rd_chunk,"little",signed=False),
             max_tar,
             tar_lock)
             )


def write_TURBO_ACTIVATION_RATIO(max_tar, core=0):
  wrmsr(0x64C, max_tar.to_bytes(1,byteorder="little"), core)


##### MSR 64Dh PLATFORM ENERGY STATUS ################################################################
def read_PLATFORM_ENERGY_STATUS(core=0):
  rd_chunk=rdmsr(0x64D, 8, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  timestamp, energy= bitstruct.unpack("u32 u32", swapped)

  # not pultiplying by energy unit because ... am not sure of the unit
  return timestamp, energy
  

##### MSR 64Fh CORE PERF LIMIT REASONS ###############################################################
def read_CORE_PERF_LIMIT_REASONS(core=0):
  rd_chunk=rdmsr(0x64F, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  clipped_any_log,tvb_log,turbo_atten_log,max_turbo_limit_log,pbm_pl2_log,pbm_pl1_log,_, \
    other_log,vr_tdc_log,vr_thermalert_log,ratl_log,rsr_limit_log,peci_pcs_limit_log,_, \
    thermal_log,prochot_log,clipped_any,tvb,turbo_atten,max_turbo_limit,pbm_pl2,pbm_pl1,_, \
    other,vr_tdc,vr_thermalert,ratl,rsr_limit,peci_pcs,_,thermal,prochot= bitstruct.unpack("b1"*32, swapped)

  # 31
  if clipped_any_log:
    print("""tripped 14 to 0""")
    # 14
    if tvb:
      print("thermal velocity boost has caused IA frequency clipping")  
    # 13
    if turbo_atten:
      print("turbo attenuation (multi core turbo) has caused IA frequency clipping")
    # 12
    if max_turbo_limit:
      print("max turbo limit has caused IA frequency clipping")
    # 11
    if pbm_pl2:
      print("PBM PL2 or PL3 (pkg, platform) has caused IA frequency clipping")
    # 10
    if pbm_pl1:
      print("PBM PL1, package or platform) has caused IA frequency clipping")
    # 8
    if other:
      print("other (IccMax, PL4, etc) has caused IA frequency clipping")
    # 7
    if vr_tdc:
      print("VR TDC (thermal design current) has caused IA frequency clipping")
    # 6
    if vr_thermalert:
      print("Hot VR (any processor VR) has caused IA frequency clipping")
    # 5
    if ratl:
      print("Running Average Thermal Limit has caused IA frequency clipping")
    # 4  
    if rsr_limit:
      print("Residency state regulation has caused IA frequency clipping")
    # 3
    if peci_pcs_limit:
      print("IA frequency has been clipped due to PECI-PCS limit")
    # 1
    if thermal:
      print("Thermal event has caused IA frequency clipping")
    # 0
    if prochot:
      print("prochot has caused IA frequency clipping")
        
  # 30  
  if tvb_log:
    print("thermal velocity boost has caused IA frequency clipping")
  # 29  
  if turbo_atten_log:
    print("turbo attenuation (multi core turbo) has caused IA frequency clipping")  
  # 28
  if max_turbo_limit:
    print("max turbo limit has caused IA frequency clipping")  
  # 27  
  if pbm_pl2_log:
    print("PBM PL2 or PL3 (in package or platform) has caused IA frequency clipping")
  # 26  
  if pbm_pl1_log:
    print("PBM PL1 (in package or platform) has caused IA frequency clipping")
  # 24
  if other_log:
    print("other (IccMax, PL4, etc) has caused IA frequency clipping")
  # 23
  if vr_tdc_log:
    print("VR TDC (thermal design current) has caused IA frequency clipping")
  # 22
  if vr_thermalert_log:
    print("Hot VR (any processor VR) has caused IA frequency clipping")
  # 21
  if ratl_log:
    print("Running Average Thermal Limit has caused IA frequency clipping")
  # 20
  if rsr_limit_log:
    print("Residency state regulation has caused IA frequency clipping")
  # 19  
  if peci_pcs_limit_log:
    print("IA frequency has been clipped due to PECI-PCS limit")
  # 17
  if thermal_log:
    print("Thermal event has caused IA frequency clipping")
  # 16
  if prochot_log:
    print("prochot has caused IA frequency clipping")

  return
  

def reset_CORE_PERF_LIMIT_REASONS(core=0):
  rd_chunk=rdmsr(0x64F, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  myint=bitstruct.unpack("u32", swapped)[0]
  wrmsr(0x64F, ((myint <<1)>>1).to_bytes(4,byteorder="little",signed=False), core)
  # wrmsr(0x64F, int(0).to_bytes(4,byteorder='little',signed=False), core)


##### MSR 665h PLATFORM_POWER_INFO ###################################################################
def read_PLATFORM_POWER_INFO(core=0):
  rd_chunk=rdmsr(0x665, 8, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  max_tw,max_ppl2,min_ppl1,max_ppl1= bitstruct.unpack("p8 u7 u17 u15 u17", swapped)
  
  return max_tw   * pcu[ "time_unit" ], \
         max_ppl2 * pcu[  "pwr_unit" ], \
         min_ppl1 * pcu[  "pwr_unit" ], \
         max_ppl1 * pcu[  "pwr_unit" ]
  

def write_PLATFORM_POWER_INFO( max_tw, max_ppl2, min_ppl1, max_ppl1, core=0):
  max_tw   = int( max_tw   / pcu[ "time_unit" ] ) 
  max_ppl2 = int( max_ppl2 / pcu[ "pwr_unit" ] )
  min_ppl1 = int( min_ppl1 / pcu[ "pwr_unit" ] )
  max_ppl1 = int( max_ppl1 / pcu[ "pwr_unit" ] )

  swapped=bitstruct.pack("p8 u7 u17 u15 u17", max_tw, max_ppl2, min_ppl1, max_ppl1)
  wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
  wrmsr(0x665, wr_chunk, core)


##### MSR 666h PLATFORM RAPL SOCKET PERF STATUS ######################################################
def read_PLATFORM_RAPL_SOCKET_PERF_STATUS(core=0):
  rd_chunk=rdmsr(0x666, 4, core)
  swapped=bitstruct.byteswap("{}".format(len(rd_chunk)),rd_chunk)
  count= bitstruct.unpack("u32", swapped)[0]

  # not multiplying by energy unit because ... am not sure of the unit
  return count
  

###################################################################################################
#
#  2. Everybody needs an init
#
###################################################################################################

def init():
  # let's read the MSR_RAPL_POWER_UNIT to initialize the fundamental units
  msr=rdmsr(0x606, 4)
  msr=bitstruct.byteswap("{}".format(len(msr)),msr)
  msr_time_unit,msr_energy_unit,msr_pwr_unit = bitstruct.unpack("p12 u4 p4 u4 p4 u4", msr)
  pcu[  "time_unit"]=1/2**msr_time_unit
  pcu["energy_unit"]=1/2**msr_energy_unit
  pcu[   "pwr_unit"]=1/2**msr_pwr_unit
