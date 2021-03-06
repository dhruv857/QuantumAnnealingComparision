# Copyright 2018 D-Wave Systems Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import time
import dimod
from neal import SimulatedAnnealingSampler
from dwave.system.testing import MockDWaveSampler

from hybrid.samplers import *
from hybrid.core import State


class MockDWaveReverseAnnealingSampler(MockDWaveSampler):
    """Extend the `dwave.system.testing.MockDWaveSampler` with mock support for
    reverse annealing.
    """
    # TODO: move to dwave-system

    def validate_anneal_schedule(self, anneal_schedule):
        return True

    def sample(self, *args, **kwargs):
        self.anneal_schedule = kwargs.pop('anneal_schedule', None)
        self.initial_state = kwargs.pop('initial_state', None)
        return super(MockDWaveReverseAnnealingSampler, self).sample(*args, **kwargs)


class TestQPUSamplers(unittest.TestCase):

    def test_unstructured_child_sampler(self):
        q = QPUSubproblemAutoEmbeddingSampler(qpu_sampler=SimulatedAnnealingSampler())

        # test sampler stays unstructured
        self.assertFalse(isinstance(q.sampler, dimod.Structured))

        # test sampling works
        bqm = dimod.BinaryQuadraticModel({'a': 1}, {}, 0, 'SPIN')
        init = State.from_subsample({'a': 1}, bqm)
        res = q.run(init).result()
        self.assertEqual(res.subsamples.first.energy, -1)

    def test_structured_child_sampler(self):
        q = QPUSubproblemAutoEmbeddingSampler(qpu_sampler=MockDWaveSampler())

        # test sampler is converted to unstructured
        self.assertFalse(isinstance(q.sampler, dimod.Structured))

        # test sampling works
        bqm = dimod.BinaryQuadraticModel({'a': 1}, {}, 0, 'SPIN')
        init = State.from_subsample({'a': 1}, bqm)
        res = q.run(init).result()
        self.assertEqual(res.subsamples.first.energy, -1)

    def test_reverse_annealing_sampler(self):
        sampler = MockDWaveReverseAnnealingSampler()
        ra = ReverseAnnealingAutoEmbeddingSampler(qpu_sampler=sampler)

        # test sampling works
        bqm = dimod.BinaryQuadraticModel({'a': 1}, {}, 0, 'SPIN')
        state = State.from_subsample({'a': 1}, bqm)
        res = ra.run(state).result()

        self.assertEqual(res.subsamples.first.energy, -1)
        self.assertEqual(sampler.initial_state.popitem()[1], 1)
        self.assertEqual(sampler.anneal_schedule, ra.anneal_schedule)


class TestTabuSamplers(unittest.TestCase):

    def test_tabu_problem_sampler_interface(self):
        bqm = dimod.BinaryQuadraticModel({'a': 1}, {}, 0, 'SPIN')

        workflow = TabuProblemSampler(num_reads=10)

        init = State.from_sample({'a': 1}, bqm)
        result = workflow.run(init).result()

        self.assertEqual(result.samples.first.energy, -1)
        self.assertEqual(len(result.samples), 10)

    def test_tabu_problem_sampler_functionality(self):
        bqm = dimod.BinaryQuadraticModel({}, {'ab': 1, 'bc': -1, 'ca': 1}, 0, 'SPIN')

        workflow = TabuProblemSampler()

        # use random sample as initial value
        init = State(problem=bqm, samples=None)
        result = workflow.run(init).result()

        self.assertEqual(result.samples.first.energy, -3)
        self.assertEqual(len(result.samples), 1)

    def test_tabu_subproblem_sampler(self):
        bqm = dimod.BinaryQuadraticModel({}, {'ab': 1, 'bc': -1, 'ca': 1}, 0, 'SPIN')

        workflow = TabuSubproblemSampler()

        # use random sample as initial value
        init = State(subproblem=bqm, subsamples=None)
        result = workflow.run(init).result()

        self.assertEqual(result.subsamples.first.energy, -3)
        self.assertEqual(len(result.subsamples), 1)

    def test_interruptable_tabu(self):
        bqm = dimod.BinaryQuadraticModel({}, {'ab': 1, 'bc': -1, 'ca': 1}, 0, 'SPIN')

        workflow = InterruptableTabuSampler()

        init = State(problem=bqm)
        future = workflow.run(init)
        while len(workflow.runnable.timers.get('dispatch.next', ())) < 1:
            time.sleep(0)

        workflow.stop()

        self.assertEqual(future.result().samples.first.energy, -3)
        self.assertGreater(len(workflow.timers['dispatch.next']), 0)
