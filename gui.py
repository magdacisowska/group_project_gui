from PyQt5 import QtWidgets, uic
import pretty_midi as md
import music21
import sys
import os
from sequence_generator import generate_vocab, generate_sequence, generate_song, music_generator, convert_string_to_sequence


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi('FrmAIMusicComposerMain.ui', self)

        # list styles
        self.cbStyle.addItems(["Energetic", "Eccentric", "Electric", "Melodic"])

        # buttons
        self.btnGenerate.clicked.connect(self.generate)
        self.btnAdjustTempo.clicked.connect(self.adjust_tempo)
        self.btnPlay.clicked.connect(self.play_output)
        self.horizontalSlider.valueChanged.connect(self.show_tempo)

        self.instrument_1 = "Electric Piano 1"
        self.instrument_2 = "Electric Piano 1"
        self.instrument_3 = "Electric Piano 1"
        os.chdir("models/")

        filelist = [f for f in os.listdir("generated/") if f.endswith(".mid")]
        if not filelist.__contains__("output.mid"):
            self.btnPlay.setEnabled(False)
            self.btnAdjustTempo.setEnabled(False)

        self.show()
        self.show_tempo()

    def show_tempo(self):
        self.label_21.setText(str(self.horizontalSlider.value()*4))

    def open_file_dialog(self):
        song_directory = str(QtWidgets.QFileDialog.getOpenFileName()[0])
        self.txtMidiFile.setText(song_directory)

    def play_output(self):
        os.startfile('generated\\output.mid')

    def adjust_tempo(self):
        new_tempo = self.horizontalSlider.value() * 4

        # song and drums separately
        file = None
        while file is None:
            file = music21.converter.parse("generated/generated.mid")
        s = music21.stream.Stream()
        for n in file.flat.notes:
            s.append(n)
        s.insert(0, music21.tempo.MetronomeMark(number=new_tempo))
        s.write('midi', fp='generated/generated.mid')

        file2 = None
        while file2 is None:
            file2 = music21.converter.parse("generated/drums.mid")
        s2 = music21.stream.Stream()
        for n in file2.flat.notes:
            s2.append(n)
        s2.insert(0, music21.tempo.MetronomeMark(number=new_tempo))
        s2.write('midi', fp='generated/drums_faster.mid')

        drums_data = md.PrettyMIDI("generated/drums_faster.mid")
        drums_output = md.PrettyMIDI()
        drums = md.Instrument(is_drum=True, program=1)
        for instrument in drums_data.instruments[0:100]:
            for note in instrument.notes:
                drums.notes.append(note)
        drums_output.instruments.append(drums)
        drums_output.write('generated/drums.mid')

        self.split_to_channels()

    def generate(self):
        self.lblError.clear()           # reset error

        generated_length = self.sbLength.value()*16     # 1 bar = 16 steps
        generated_tempo = self.horizontalSlider.value() * 4
        generated_style = self.cbStyle.currentText()
        sequence_granularity = self.sbGranular.value()
        sequence_length = self.sbSeqLength.value()

        model_number = 0
        if generated_style == "Energetic":
            model_number = 0
            self.instrument_1 = "Acoustic Bass"
            self.instrument_2 = "Percussive Organ"
            self.instrument_3 = "Electric Piano 2"
        elif generated_style == "Eccentric":
            model_number = 1
            self.instrument_1 = "Acoustic Bass"
            self.instrument_2 = "Percussive Organ"
            self.instrument_3 = "FX 3 (crystal)"
        elif generated_style == "Electric":
            model_number = 2
            self.instrument_1 = "Synth Bass 2"
            self.instrument_2 = "Percussive Organ"
            self.instrument_3 = "Clarinet"
        elif generated_style == "Melodic":
            model_number = 3
            self.instrument_1 = "Synth Bass 1"
            self.instrument_2 = "Percussive Organ"
            self.instrument_3 = "Electric Piano 2"

        # clear directories
        filelist = [f for f in os.listdir("generated/") if f.endswith(".mid")]
        for f in filelist:
            os.remove(os.path.join("generated/", f))
        filelist = [f for f in os.listdir("generated/drums/") if f.endswith(".mid")]
        for f in filelist:
            os.remove(os.path.join("generated/drums/", f))

        if self.chbSequence.isChecked():
            try:
                # ---- use sequence generator -----
                if len(self.textEdit.toPlainText()) > 0:
                    # blocks = generate_vocab(len(self.textEdit.toPlainText()), 1)
                    sequence = convert_string_to_sequence(self.textEdit.toPlainText())      # use user sequence
                else:
                    blocks = generate_vocab(sequence_length, 1)
                    sequence = generate_sequence(sequence_length, blocks)                   # random otherwise

                print(sequence)
                generate_song(sequence, model=model_number, granurality=sequence_granularity)

                # change tempo of generated song
                # file = music21.converter.parse("current_midi.mid")            # todo: tempo changing
                file = md.PrettyMIDI("current_midi.mid")

            except IndexError:
                # in case of Magenta creating empty sequence (can happen sometimes)
                self.lblError.setText("Internal Magenta error: empty sequence")
                self.lblError.setStyleSheet('color: red')
                return

        else:
            # ---- basic generation -----
            os.system('polyphony_rnn_generate'
                      ' --run_dir=training_data_' + str(model_number) + '/polyphony_rnn/logdir/run1'
                      ' --hparams="batch_size=64,rnn_layer_sizes=[128,128,128]"'
                      ' --output_dir=generated'
                      ' --num_outputs=1'
                      ' --num_steps=' + str(generated_length) +
                      ' --condition_on_primer=true --inject_primer_during_generation=false')

            # change tempo of generated song
            filelist = [f for f in os.listdir("generated/") if f.endswith(".mid")]
            # file = music21.converter.parse("generated/" + filelist[0])                        # todo: tempo changing
            file = md.PrettyMIDI("generated/" + filelist[0])

        # s = music21.stream.Stream()                                           # todo: tempo changing
        # for n in file.flat.notes:
        #     s.append(n)
        # s.insert(0, music21.tempo.MetronomeMark(number=generated_tempo))
        # s.write('midi', fp='generated/generated.mid')
        file.write("generated/generated.mid")

        # generate drums fitting the song
        os.system('drums_rnn_generate --config="one_drum"'
                  ' --run_dir=drums_rnn/logdir/run2 --hparams="batch_size=64,rnn_layer_sizes=[64,64]"'
                  ' --output_dir=generated/drums --num_outputs=1'
                  ' --num_steps=' + str(len(md.PrettyMIDI("generated/generated.mid").get_downbeats()) * 8 + 4) +
                  ' --condition_on_primer=true'
                  ' --inject_primer_during_generation=false --primer_midi=generated/generated.mid')

        filelist = [f for f in os.listdir("generated/drums/") if f.endswith(".mid")]
        drums = md.PrettyMIDI("generated/drums/" + filelist[0])
        drums.write("generated/drums.mid")

        # split into 3 channels according to style
        self.split_to_channels()

        self.btnPlay.setEnabled(True)
        self.btnAdjustTempo.setEnabled(True)

    def split_to_channels(self):
        midi_data = md.PrettyMIDI("generated/generated.mid")
        drums_data = md.PrettyMIDI("generated/drums.mid")
        output_midi = md.PrettyMIDI()

        bass = md.Instrument(program=md.instrument_name_to_program(self.instrument_1))
        guitar = md.Instrument(program=md.instrument_name_to_program(self.instrument_2))
        piano = md.Instrument(program=md.instrument_name_to_program(self.instrument_3))

        for instrument in midi_data.instruments:
            pitches = [note.pitch for note in instrument.notes]
            pitches.sort()

            bass_tresh = pitches[int(len(pitches) / 4)]
            guitar_tresh = pitches[int(2 * len(pitches) / 3)]

            for note in instrument.notes:
                if note.pitch < bass_tresh:
                    bass.notes.append(note)
                elif note.pitch < guitar_tresh:
                    guitar.notes.append(note)
                else:
                    piano.notes.append(note)

        output_midi.instruments.append(bass)
        output_midi.instruments.append(guitar)
        output_midi.instruments.append(piano)

        if drums_data:
            for drum_item in drums_data.instruments:
                output_midi.instruments.append(drum_item)

        output_midi.write('generated/output.mid')


app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()
