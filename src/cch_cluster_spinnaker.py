'''
This is a local version of the UP task to calculate all pairwise CCHs and their
significance based on 1000 spike dither surrogates on the PBS based cluster.
'''

# =============================================================================
# Initialization
# =============================================================================

# this number relates to the "-t" parameter:
#   -t 0-X => num_tasks=X+1
num_tasks = 100

# get job parameter
import os
import sys
PBS_value = os.getenv('PBS_ARRAYID')
if PBS_value is not None:
    job_parameter = int(PBS_value)
else:
    job_parameter = 1


# to find our "special" elephant
sys.path.insert(1, '..')
# change this to point to your reachgrasp IO
sys.path.insert(1, '../../dataset_repos/reachgrasp/python')
sys.path.insert(1, '../../toolboxes/py/python-neo')
sys.path.insert(1, '../../toolboxes/py/python-odml')
sys.path.insert(1, '../../toolboxes/py/csn_toolbox')

import numpy as np
import quantities as pq

# provides neo framework and I/Os to load exp and mdl data
import neo

# provides core analysis library component
import elephant
import elephant.spike_train_correlation as stc
import elephant.conversion as conv

def cch_measure(cch_all_pairs):
    ind = np.argmin(np.abs(cch_all_pairs.times))
    return np.sum(cch_all_pairs[ind - 5:ind + 5].magnitude)


# =============================================================================
# Global variables
# =============================================================================

# duration of recording to load
rec_start = 10.*pq.s
duration = 50.*pq.s


# =============================================================================
# Load experimental data
# =============================================================================

filename = '../../data/Spinnaker_Data/results/spikes_L5E.h5'
session = neo.NeoHdf5IO(filename=filename)
block = session.read_block()
sts_spinnaker=block.list_children_by_class(neo.SpikeTrain)[:100]
print("Number of spinnaker spike trains: " + str(len(sts_spinnaker)))


# =============================================================================
# Load simulation data
# =============================================================================

filename = '../../data/Nest_Data/collected_spikes_L4E-77177.h5'
session = neo.NeoHdf5IO(filename=filename)

sts_nest = []

for k in range(100):
    sts_nest.append(session.get("/" + "SpikeTrain_" + str(k)))


print("Number of nest spike trains: " + str(len(sts_nest)))
#
#


# ## Cross-correlograms
num_surrs = 1
max_lag_bins = 200
lag_res = 1 * pq.ms
max_lag = max_lag_bins * lag_res
smoothing = 10 * pq.ms

num_neurons_spinnaker = len(sts_spinnaker)
num_ccs = (num_neurons_spinnaker ** 2 - num_neurons_spinnaker) / 2

cc = {}
for dta in ['spinnaker', 'nest']:
    cc[dta] = {}
    cc[dta]['unit_i'] = {}
    cc[dta]['unit_j'] = {}
    cc[dta]['times_ms'] = {}
    cc[dta]['original'] = {}
    cc[dta]['surr'] = {}
    cc[dta]['original_measure'] = {}
    cc[dta]['surr_measure'] = {}
    cc[dta]['pvalue'] = {}

# create all combinations of tasks
num_total_pairs = 0
all_combos_unit_i = []
all_combos_unit_j = []
for ni in range(num_neurons_spinnaker):
    for nj in range(ni, num_neurons_spinnaker):
        all_combos_unit_i.append(ni)
        all_combos_unit_j.append(nj)
        num_total_pairs += 1

# calculate indices in cc['unit_i'] list which to calculate for each task
idx = np.linspace(0, num_total_pairs, num_tasks + 1, dtype=int)
task_starts_idx = idx[:-1]
task_stop_idx = idx[1:]

print("Task Nr.: %i" % job_parameter)
print("Number of tasks: %i" % num_tasks)

for dta, sts in zip(['spinnaker', 'nest'], [sts_spinnaker, sts_nest]):
    for calc_i in range(
            task_starts_idx[job_parameter], task_stop_idx[job_parameter]):
        # save neuron i,j index
        ni = all_combos_unit_i[calc_i]
        nj = all_combos_unit_j[calc_i]

        cc[dta]['unit_i'][calc_i] = ni
        cc[dta]['unit_j'][calc_i] = nj

        print("Correlating %i and %i" % (ni, nj))

        # original CCH
        cco = stc.corrcoef(
            conv.BinnedSpikeTrain(sts[ni], lag_res) , conv.BinnedSpikeTrain(
            sts[nj],lag_res))
        cc[dta]['original_measure'][calc_i] = cco

        surr_i = elephant.spike_train_surrogates.dither_spikes(
            sts[ni], dither=50. * pq.ms, n=num_surrs)
        surr_j = elephant.spike_train_surrogates.dither_spikes(
            sts[nj], dither=50. * pq.ms, n=num_surrs)

        ccs = []
        ccsm = []
        for surrogate in range(num_surrs):
            scc = stc.corrcoef(conv.BinnedSpikeTrain(
                surr_i[surrogate], lag_res), conv.BinnedSpikeTrain(
                surr_j[surrogate], lag_res))
            ccs.append(scc)
        cc[dta]['surr_measure'][calc_i] = ccs
        cc[dta]['pvalue'][calc_i] = np.count_nonzero(np.array(ccs) >= cco)

## write parameters to disk
#import h5py_wrapper.wrapper
#filename = '../../results/hbp_review_task/correlation_output_'
#if os.path.exists(filename):
#    os.remove(filename)
#h5py_wrapper.wrapper.add_to_h5(
#    filename +
#    str(job_parameter) + '.h5',
#    cc, write_mode='w', overwrite_dataset=True)
import h5py
filename = '../../results/hbp_review_task/correlation_output_'
if os.path.exists(filename):
    os.remove(filename)
f = h5py.File(filename + str(job_parameter) + '.h5', 'w')
for k,v in cc.items():
    dataset = f.create_dataset(k, data=v)
f.close()