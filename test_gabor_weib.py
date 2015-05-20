# -*- coding: utf-8 -*-

# add description

# TODOs:
# [ ] add instructions     (!)
# [ ] add stepwise constrast checking
# [ ] we need to log age and sex of the participant
#     (that would go to settings.py)
# [ ] add markers to:
#     -> start (and end?) of each break
#     -> 
# [ ] test continue_dataframe for overwrite
# 
# not necessary:
# [ ] load seaborn conditionally

# imports
from psychopy  import visual, core, event, logging
from ctypes    import windll
from weibull   import Weibull
from exputils  import plot_Feedback
from stimutils import exp, db, stim, startTrial, present_trial, \
					  present_break, show_resp_rules, \
					  present_feedback, give_training_db, \
					  Instructions
import os
import numpy  as np
import pandas as pd


# set loggingly logging to logfile
lg = logging.LogFile(f=exp['logfile'], level=logging.INFO, filemode='w')

# a remainging def, could be moved to weibull module, but uses logging
# and weibull module should not import psychopy
def correct_Weibull_fit(w, exp, newopac):
	# log weibul fit and contrast
	logging.info( 'Weibull params:  {} {}'.format( *w.params ) )
	logging.info( 'Contrast limits set to:  {0} - {1}'.format(*newopac) )

	# TODO this needs checking, removing duplicates and testing
	if newopac[1] < 0.005 or newopac[1] <= newopac[0] or w.params[0] < 0 \
		or newopac[1] < 0.01 or newopac[0] > 1.0:

		set_opacity_if_fit_fails(w.orig_y, exp)
		logging.info( 'Weibull fit failed, contrast set to:  {0} - {1}'.format(*exp['opacity']) )
	else:
		exp['opacity'] = newopac

	# additional contrast checks
	precheck_opacity = exp['opacity'].copy()
	if exp['opacity'][1] > 1.0:
		exp['opacity'][1] = 1.0
	if exp['opacity'][0] < 0.01:
		exp['opacity'][0] = 0.01
	if exp['opacity'][0] > exp['opacity'][1]:
		exp['opacity'][0] = exp['opacity'][1]/2

	if not (exp['opacity'] == precheck_opacity):
		logging.info('Opacity limits corrected to:  {0} - {1}'.format(*exp['opacity']))

	# log messages
	logging.flush()

	return exp


# EXPERIMENT
# ==========

# INSTRUCTIONS!
instr = Instructions('instructions.yml')
instr.present()

# show response rules:
show_resp_rules()

# SLOW TRAINING
# -------------

# set things up
slow = exp.copy()
slow['opacity'] = [0.7, 1.0]
train_db = give_training_db(db, slowdown=5)

i = 1
training_correctness = 0
while training_correctness < exp['train corr'][0] or i < 14:
	present_trial(i, exp=slow, db=train_db)

	# feedback:
	present_feedback(i, db=train_db)
	# check correctness
	training_correctness = train_db.loc[1:i, 'ifcorrect'].mean()
	i += 1


# signal that main proc is about to begin
# ---------------------------------------
windll.inpout32.Out32(exp['port']['port address'], 255)
show_resp_rules()

# TODO - info that main experiment is about to begin

# MAIN EXPERIMENT
# ---------------
for i in range(startTrial, exp['numTrials'] + 1):
	present_trial(i)
	stim['window'].flip()

	# present break 
	if (i) % exp['break after'] == 0:
		# save data before every break
		db.to_excel(os.path.join(exp['data'], exp['participant'] + '.xls'))

		# TODO: close this into a def
		# if break was within first 100 trials,
		# fit Weibull function
		if i <= exp['fit until']:

			# fitting psychometric function
			w = fit_weibull(db, i)
			newopac = w._dist2corr(exp['corrLims'])
			exp = correct_Weibull_fit(w, exp, newopac)

			# show weibull fit
			plot_Feedback(stim, w, exp['data'])

		# break and refresh keyboard mapping
		present_break(i)
		show_resp_rules()

	stim['window'].flip()
	core.wait(0.5) # pre-fixation time is always the same

db.to_excel(os.path.join(exp['data'], exp['participant'] + '.xls'))
core.quit()