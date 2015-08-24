# -*- coding: utf-8 -*-

# add description

# TODOs:
# [.] add instructions     (!)
# [ ] add markers to:
#     -> start (and end?) of each break
#     ->


# imports
# -------
from psychopy  import visual, core, event, logging

import os
import numpy  as np
import pandas as pd
from exputils  import (plot_Feedback, create_database,
	ContrastInterface, DataManager, ExperimenterInfo,
	AnyQuestionsGUI, ms2frames)
from utils     import to_percent, round2step, trim_df
from weibull   import fitw, get_new_contrast, correct_weibull
from stimutils import (exp, db, stim, present_trial,
	present_break, show_resp_rules, textscreen,
	present_feedback, present_training, trim,
	give_training_db, Instructions, Stepwise,
	TimeShuffle, onflip_work, clear_port)

if os.name == 'nt' and exp['use trigger']:
	from ctypes import windll

# set logging
dm = DataManager(exp)
exp = dm.update_exp(exp)
exp['numTrials'] = 500
log_path = dm.give_path('l', file_ending='log')
lg = logging.LogFile(f=log_path, level=logging.WARNING, filemode='w')

# TODO: check for continue?
# if fitting completed -> use data
# if c part done -> use data
# check via dm.give_previous_path('b') etc.
exp_info = ExperimenterInfo(exp, stim)

# INSTRUCTIONS
# ------------
if exp['run instruct']:
	instr = Instructions('instructions.yaml')
	instr.present(stop=8)
	show_resp_rules(exp=exp, text=u"Tak wygląda ekran przerwy.")
	instr.present(stop=12)
	# "are there any questions" GUI:
	qst_gui = AnyQuestionsGUI(exp, stim)
	qst_gui.run()
	instr.present(stop=13)


# show response rules:
show_resp_rules(exp=exp, text=(u"Zaraz rozpocznie się trening." +
	u"\nPrzygotuj się.\nPamiętaj o pozycji palców na klawiaturze."))

# TRAINING
# --------
if exp['run training']:
	# send start trigger:
	onflip_work(exp['port'], code='training')
	clear_port(exp['port'])

	# set things up
	slow = exp.copy()
	df_train = []
	num_training_blocks = len(exp['train slow'])
	current_block = 0

	slow['opacity'] = [1.0, 1.0]
	txt = u'Twoja poprawność: {}\nOsiągnięto wymaganą poprawność.\n'
	addtxt = (u'Szybkość prezentacji bodźców zostaje zwiększona.' +
		u'\nAby przejść dalej naciśnij spację.')

	for s, c in zip(exp['train slow'], exp['train corr']):
		# present current training block until correctness is achieved
		df, current_corr = present_training(exp=slow, slowdown=s, corr=c)
		current_block += 1

		# update experimenter info:
		exp_info.training_info([current_block, num_training_blocks],
			current_corr)

		# show info for the subject:
		if s == 1:
			addtxt = (u'Koniec treningu.\nAby przejść dalej ' +
				u'naciśnij spację.')
		now_txt = txt + addtxt
		textscreen(now_txt.format(to_percent(current_corr)))
		show_resp_rules(exp=exp)

		# concatenate training db's (and change indexing)
		if df_train:
			df_train = pd.concat([df_train, trim_df(df)])
			df_train.index = np.r_[1:df_train.shape[0]+1]
		else:
			df_train = trim_df(df)

	# save training database:
	df_train.to_excel(dm.give_path('a'))


# ADD some more instructions here
# TODO - info that main experiment is about to begin

# Contrast fitting - stepwise
# ---------------------------
if exp['run fitting']:
	# some instructions
	if exp['run instruct']:
		instr.present(stop=15)

	# send start trigger:
	onflip_work(exp['port'], code='fitting')
	clear_port(exp['port'])

	# update experimenters view:
	block_name = 'schodkowe dopasowywanie kontrastu'
	exp_info.blok_info(block_name, [0, 100])

	# init stepwise contrast adjustment
	num_fail = 0
	continue_fitting = True
	step = exp['step until']
	exp['opacity'] = [1., 1.]
	s = Stepwise(corr_ratio=[1,1])
	fitting_db = give_training_db(db, slowdown=1)

	while s.trial <= step[0] and len(s.reversals) < 3:
		present_trial(s.trial, db=fitting_db, exp=exp)
		exp_info.blok_info(block_name, [s.trial, 100])
		stim['window'].flip()

		s.add(fitting_db.loc[s.trial, 'ifcorrect'])
		c = s.next()
		exp['opacity'] = [c, c]
		if (s.trial % 10) == 0:
			show_resp_rules(exp=exp)


	# more detailed stepping now
	last_trial = s.trial - 1
	start_param = np.mean(s.reversals) if \
		len(s.reversals) > 1 else s.param
	s = Stepwise(corr_ratio=[2,1], start=s.param, vmin=0.025,
		step=[0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.025, 0.025, 0.025])

	trial = s.trial + last_trial
	while trial <= step[1]:
		trial = s.trial + last_trial
		present_trial(trial, db=fitting_db, exp=exp)
		stim['window'].flip()

		# update experimenter
		exp_info.blok_info(block_name, [trial, 100])

		# get contrast from Stepwise
		s.add(fitting_db.loc[trial, 'ifcorrect'])
		c = s.next()
		exp['opacity'] = [c, c]
		if (trial % 10) == 0:
			show_resp_rules(exp=exp)

	mean_thresh = np.mean(s.reversals) if s.reversals else c
	# save fitting dataframe
	fitting_db.to_excel(dm.give_path('b'))


	# Contrast fitting - weibull
	# --------------------------
	trial += 1
	params = [1., 1.]

	# add param columns to fitting db
	fitting_db['w1'] = np.nan
	fitting_db['w2'] = np.nan

	check_contrast = np.arange(mean_thresh-0.05,
		mean_thresh+0.1, 0.05)
	# make sure to trim and 'granularize' check_contrast
	check_contrast = np.array( [trim(x, exp['min opac'], 
		1.) for x in check_contrast] )

	while (trial <= exp['fit until'] or
		continue_fitting) and trial <= exp['max fit']:

		# remind about the button press mappings
		show_resp_rules(exp=exp)

		# shuffle trials and present them all
		np.random.shuffle(check_contrast)
		for c in check_contrast:
			exp['opacity'] = [c, c]
			present_trial(trial, db=fitting_db, exp=exp)
			stim['window'].flip()
			trial += 1

		# fit weibull
		look_back = min(trial-1, 75)
		ind = np.r_[trial-look_back:trial]
		w = fitw(fitting_db, ind)
		params = w.params

		# save weibull params in fitting_db and save to disk:
		fitting_db.loc[trial-1, 'w1'] = params[0]
		fitting_db.loc[trial-1, 'w2'] = params[1]
		save_df = trim_df(fitting_db)
		save_df.to_excel(dm.give_path('b'))

		# contrast corrections, choosing new contrast samples
		contrast_range, num_fail = correct_weibull(w, num_fail, df=fitting_db)
		check_contrast, contrast_range = get_new_contrast(w, corr_lims=exp['fitCorrLims'],
			method=exp['search method'], contrast_lims=contrast_range)
		print check_contrast

		# show weibull fit
		stim = plot_Feedback(stim, w, exp['data'])
		interf = ContrastInterface(stim=stim, trial=trial)

		interfaceLoop = True
		# stim['window'].units = 'norm'
		while interfaceLoop:
			interf.refresh()
			k = event.getKeys()
			if k and 'q' in k or 'return' in k:
				interfaceLoop = False
			if interf.buttons[1].clicked:
				interfaceLoop = False
				continue_fitting = False
			elif interf.buttons[0].clicked:
				interfaceLoop = False
				continue_fitting = True
		interf.quit()
		if len(interf.contrast) > 0:
			check_contrast = interf.contrast
		print 'interface contrast: ', interf.contrast


	# save fitting dataframe
	trim_df(fitting_db).to_excel(dm.give_path('b'))

# EXPERIMENT - part c
# -------------------
if exp['run main c']:
	# instructions
	if exp['run instruct']:
		instr.present(stop=16)

	# send trigger
	onflip_work(exp['port'], 'contrast')
	clear_port(exp['port'])

	# get contrast from training
	if 'contrast_range' not in locals():
		contrast_range = [0.95, 0.1]

	contrast_steps = np.linspace(contrast_range[0],
		contrast_range[1], exp['opac steps'])
	db_c = create_database(exp, combine_with=('opacity',
		contrast_steps), rep=13)
	exp['numTrials'] = len(db_c.index)

	# signal that main proc is about to begin
	if exp['use trigger']:
		windll.inpout32.Out32(exp['port']['port address'], 255)
		core.wait(0.01)
		clear_port(exp['port'])

	# main loop
	for i in range(1, db_c.shape[0] + 1):
		present_trial(i, exp=exp, db=db_c, use_exp=False)
		stim['window'].flip()

		# present break
		if (i) % exp['break after'] == 0:
			# save data before every break
			db_c.to_excel(dm.give_path('c'))
			# break and refresh keyboard mapping
			present_break(i, exp=exp)
			show_resp_rules(exp=exp)

		# inter-trial interval
		stim['window'].flip()
		exp_info.blok_info(u'główne badanie, część I', [i, exp['numTrials']])
		core.wait(0.5) # pre-fixation time is always the same

	db_c.to_excel(dm.give_path('c'))


# EXPERIMENT - part t
# -------------------

# if 'contrast_range' not in locals():
# fit weibull
# TODO - load last db_c from disk if not present in locals
w = fitw(db_c, db_c.index)
opacity = w.get_threshold([0.7])[0]
# opacity = 0.45 # temp fix

times = TimeShuffle(start=1., end=5., every=0.2,
			times=4).all()
times = ms2frames(times * 1000, exp['frm']['time'])
db_t = create_database(exp, combine_with=('fixTime', times))
db_t.loc[:, 'opacity'] = opacity

exp['numTrials'] = len(db_t.index)

if exp['run instruct']:
	instr.present()

onflip_work(exp['port'], 'time')
clear_port(exp['port'])

# signal that another proc is about to begin
if exp['use trigger']:
	windll.inpout32.Out32(exp['port']['port address'], 255)
	core.wait(0.01)
	clear_port(exp['port'])

# main loop
for i in range(1, db_t.shape[0] + 1):
	present_trial(i, exp=exp, db=db_t, use_exp=False)
	stim['window'].flip()

	# present break
	if (i) % exp['break after'] == 0:
		# save data before every break
		db_t.to_excel(dm.give_path('t'))
		# break and refresh keyboard mapping
		present_break(i, exp=exp)
		show_resp_rules(exp=exp)

	# inter-trial interval
	stim['window'].flip()
	exp_info.blok_info(u'główne badanie, część II', [i, exp['numTrials']])
	core.wait(0.5) # pre-fixation time is always the same

# save data before quit
db_t.to_excel(dm.give_path('t'))

# goodbye!
core.quit()
