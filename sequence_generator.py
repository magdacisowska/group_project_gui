import math
import random
import string
import numpy as np
import os
from itertools import combinations_with_replacement
import pretty_midi as md
import copy


def generate_vocab(length, variability=None):
    if length < 1:
        raise Exception('Sequence length cannot be smaller than 1')
    min_vocab_length = 1
    log_base = 2*math.sqrt(5)
    variability_table = [1.7, 2, log_base, 5]    # genre dependent part
    if variability is not None and variability < 4 and variability >= 0:
        log_base = variability_table[variability]
    randomness_factor = random.random() / 5
    amount_of_sections = 1 + round(math.log(length*(1+randomness_factor), log_base*(1+randomness_factor)))
    print(amount_of_sections)
    sections = []
    for i in range(amount_of_sections):
        sections.append(i)
    blocks = []
    blocks.append(None)
    blocks.append(sections)
    for i in range(2, len(sections)+1):
        blocks.append(list(combinations_with_replacement(sections, i)))
    return blocks


def generate_vocab_test():
    for i in range(10, 1000, 10):
        variability = random.randint(0, 4)
        blocks  = generate_vocab(i, variability)
        print(sections, blocks)
        input()


def generate_sequence(length, blocks):
    index = 0
    sequence = []
    while index < length:
        sequence_length = random.randint(0, 100) % (len(blocks)-1) % (length-index)+1
        sequence_index = random.randint(0, len(blocks[sequence_length])-1)
        elem = blocks[sequence_length][sequence_index]
        if type(elem) is tuple:
            for i in elem:
                sequence.append(i)
        else:
            sequence.append(elem)
        index += sequence_length
    return sequence


def convert_string_to_sequence(seq_input):
    used_chars = {}
    sequence = []
    for i in seq_input:
        if i in used_chars.keys():
            sequence.append(used_chars[i])
        else:
            index = len(used_chars.keys())
            used_chars[i] = index
            sequence.append(index)
    return sequence


class music_generator:
    def __init__(self, model, granularity):
        # initialize proper tensorflow model
        self.model_number = model
        self.used_sections = []
        self.current_midi = md.PrettyMIDI()
        self.section_midis = {}
        self.granularity = granularity

    def generate_midi(self, section):
        if len(self.used_sections) == 0:
            print("1")
            # ----- create start (base) sequence
            self.used_sections.append(section)
            os.system('polyphony_rnn_generate'
                      ' --run_dir=training_data_' + str(self.model_number) + '/polyphony_rnn/logdir/run1'
                      ' --hparams="batch_size=64,rnn_layer_sizes=[128,128,128]"'
                      ' --output_dir=sequences'
                      ' --num_outputs=1'
                      ' --num_steps=' + str(16*self.granularity) +  #str(generated_length) +
                      ' --condition_on_primer=true --inject_primer_during_generation=false')

            filelist = [f for f in os.listdir("sequences/") if f.endswith(".mid")]
            midi = md.PrettyMIDI("sequences/" + filelist[0])

            self.section_midis[str(section)] = copy.deepcopy(midi)     # generated midi is also the first sequence
            self.current_midi = copy.deepcopy(midi)            # update current midi with latest generated
            midi.write("current_midi.mid")

            # clear directory
            filelist = [f for f in os.listdir("sequences/") if f.endswith(".mid")]
            for f in filelist:
                os.remove(os.path.join("sequences/", f))

        elif section in self.used_sections:
            print("2")
            # ---- simply add previously generated midi to current midi
            offset = self.current_midi.get_end_time()           # add time offset to notes

            instrument = self.current_midi.instruments[0]
            instrument1 = copy.deepcopy(self.section_midis[str(section)].instruments[0])
            for note in instrument1.notes:
                new_note = md.Note(start=note.start + offset, end=note.end + offset, pitch=note.pitch, velocity=note.velocity)
                instrument.notes.append(new_note)

            self.current_midi.write("current_midi.mid")

        else:
            print("3")
            # ---- generate new sequence with length: current_midi + granurality [tacts], then cut out the first part
            self.used_sections.append(section)

            # run tensorflow commands to generate midi with current_midi as primer
            os.system('polyphony_rnn_generate'
                      ' --run_dir=training_data_' + str(self.model_number) + '/polyphony_rnn/logdir/run1'
                      ' --hparams="batch_size=64,rnn_layer_sizes=[128,128,128]"'
                      ' --output_dir=sequences'
                      ' --num_outputs=1'
                      ' --num_steps=' + str(16*self.granularity + 16*len(self.current_midi.get_downbeats())) +
                      ' --condition_on_primer=false --inject_primer_during_generation=true'
                      ' --primer_midi=current_midi.mid')

            # generated (longer) midi
            filelist = [f for f in os.listdir("sequences/") if f.endswith(".mid")]
            midi = md.PrettyMIDI("sequences/" + filelist[0])

            # section_midi stores only latest few bars (depending on granurality of sections)
            section_midi = md.PrettyMIDI()
            instr = md.Instrument(program=1)
            downbeats = midi.get_downbeats()

            for instrument in midi.instruments:
                for note in instrument.notes:
                    if note.start >= downbeats[len(downbeats) - self.granularity]:      # "cutting"
                        instr.notes.append(note)
            section_midi.instruments.append(instr)

            offset = section_midi.instruments[0].notes[0].start     # subtract time offset created by cutting
            for instrument in section_midi.instruments:
                for note in instrument.notes:
                    note.start -= offset
                    note.end -= offset

            section_midi.write("section.mid")
            self.section_midis[str(section)] = section_midi    # save to the section midis dict

            # append current_midi - remember about adding time offset
            offset = self.current_midi.get_end_time()
            if len(self.current_midi.instruments) > 0:
                instrument = self.current_midi.instruments[0]
                instrument1 = copy.deepcopy(section_midi.instruments[0])
                for note in instrument1.notes:
                    new_note = md.Note(start=note.start + offset, end=note.end + offset, pitch=note.pitch, velocity=note.velocity)
                    instrument.notes.append(new_note)

            self.current_midi.write("current_midi.mid")

            # clear directory
            filelist = [f for f in os.listdir("sequences/") if f.endswith(".mid")]
            for f in filelist:
                os.remove(os.path.join("sequences/", f))


def generate_song(sequence, model, granurality):
    generator = music_generator(model=model, granularity=granurality)
    for i in sequence:
        print("-------- making " + str(i) + " fragment")
        generator.generate_midi(i)
    return generator.current_midi


# if __name__ == '__main__':
#     os.chdir("models/")
#     blocks = generate_vocab(length=3, variability=1)
#     sequence = generate_sequence(length=3, blocks=blocks)
#     print(sequence)
#     generate_song(sequence, model=0, granurality=1)
#     print(sequence)
