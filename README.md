launch pcu.py on a multi socket system, running INTEL Sapphire Rapids

will display in console mode the PCU registers, updates every 200ms, for exploration.

msr.py is a library of functions to call, in order to decipher the bits of each MSR. not all MSRs have been coded.

current_exploration.py is an attempt to unlock IccMax, VR_CURRENT, and other intensity related knobs in the PCU

oc_mailbox.py is an attempt at using the OC_MAILBOX to configure TDP related limits.
