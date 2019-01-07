#!/usr/bin/env python3
import os
import subprocess
import tempfile
import logging
import shutil
from typing import Dict, Any

from profiles import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class SpeechTuner:
    '''Base class for all speech system tuners.'''
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def preload(self):
        '''Cache import stuff upfront.'''
        pass

    def tune(self, wav_intents: Dict[str, Dict[str, Any]]) -> None:
        '''Tunes a speech system with WAV file paths mapped to intents.'''
        pass

# -----------------------------------------------------------------------------
# Sphinxtrain based tuner for pocketsphinx
# https://github.com/cmusphinx/sphinxtrain
# -----------------------------------------------------------------------------

class SphinxTrainSpeechTuner(SpeechTuner):
    '''Uses sphinxtrain tools to generate an MLLR matrix for an acoustic model.'''

    def tune(self, wav_intents: Dict[str, Dict[str, Any]], mllr_path=None) -> None:
        ps_config = self.profile.get('speech_to_text.pocketsphinx')

        # Load decoder settings
        hmm_path = self.profile.read_path(ps_config['acoustic_model'])
        dict_path = self.profile.read_path(ps_config['dictionary'])

        with tempfile.TemporaryDirectory(prefix='rhasspy-') as temp_dir:
            # Create mdef.txt
            mdef_path = os.path.join(temp_dir, 'mdef.txt')
            mdef_command = ['pocketsphinx_mdef_convert',
                            '-text', os.path.join(hmm_path, 'mdef'),
                            mdef_path]

            logger.debug('Creating mdef.txt: %s' % mdef_command)
            subprocess.check_call(mdef_command)

            # Copy WAV files into temporary directory with unique names
            fileid_intents = {}
            logger.debug('Copying %s WAV file(s) to %s' % (len(wav_intents), temp_dir))
            for wav_path in list(wav_intents.keys()):
                if not os.path.exists(wav_path):
                    logger.warn('Skipping %s (does not exist)' % wav_path)
                    continue

                # Copy WAV file
                temp_wav_path = tempfile.NamedTemporaryFile(dir=temp_dir, suffix='.wav', delete=False).name
                shutil.copy(wav_path, temp_wav_path)

                # Add to new intent dict
                file_id = os.path.split(os.path.split(temp_wav_path)[1])[0]
                fileid_intents[file_id] = wav_intents[wav_path]

            # Write fileids (just the file name, no extension)
            fileids_path = os.path.join(temp_dir, 'fileids')
            with open(fileids_path, 'w') as fileids_file:
                for file_id in fileid_intents.keys():
                    print(file_id, file=fileids_file)

            logger.debug('Wrote %s fileids' % len(fileid_intents))

            # Write transcription.txt
            transcription_path = os.path.join(temp_dir, 'transcription.txt')
            with open(transcription_path, 'w') as transcription_file:
                for file_id in sorted(fileid_intents):
                    text = fileid_intents[file_id]['text'].strip()
                    print('%s (%s.wav)' % (text, file_id), file=transcription_file)

            logger.debug('Wrote %s' % transcription_path)

            # Extract features
            feat_params_path = os.path.join(hmm_path, 'feat.params')
            subprocess.check_call(['sphinx_fe',
                                    '-argfile', feat_params_path,
                                    '-samprate', '16000',
                                    '-c', fileids_path,
                                    '-di', temp_dir,
                                    '-do', temp_dir,
                                    '-ei', 'wav',
                                    '-eo', 'mfc',
                                    '-mswav', 'yes'])

            logger.debug('Extracted MFC features')

            # Generate statistics
            bw_args = ['-hmmdir', hmm_path,
                       '-dictfn', dict_path,
                       '-ctlfn', fileids_path,
                       '-lsnfn', transcription_path,
                       '-cepdir', temp_dir,
                       '-moddeffn', mdef_path,
                       '-accumdir', temp_dir,
                       '-ts2cbfn', '.cont.']  # assume continuous model

            feature_transform_path = os.path.join(hmm_path, 'feature_transform')
            if os.path.exists(feature_transform_path):
                # Required if feature transform exists!
                bw_args.extend(['-lda', feature_transform_path])

            # Add model parameters
            with open(feat_params_path, 'r') as feat_params_file:
                for line in feat_params_file:
                    line = line.strip()
                    if len(line) > 0:
                        param_parts = line.split(maxsplit=1)
                        param_name = param_parts[0]
                        # Only add compatible bw args
                        if param_name in SphinxTrainSpeechTuner.BW_ARGS:
                            # e.g., -agc none
                            bw_args.extend([param_name, param_parts[1]])

            bw_command = ['bw', '-timing', 'no'] + bw_args
            logger.debug(bw_command)
            subprocess.check_call(bw_command)

            logger.debug('Generated statistics')

            # Generate MLLR matrix
            mllr_path = mllr_path or self.profile.write_path(
                self.profile.get('tuning.sphinxtrain.mllr_matrix'))

            solve_command = ['mllr_solve',
                              '-meanfn', os.path.join(hmm_path, 'means'),
                              '-varfn', os.path.join(hmm_path, 'variances'),
                              '-outmllrfn', mllr_path,
                              '-accumdir', temp_dir]

            logger.debug(solve_command)
            subprocess.check_call(solve_command)

            logger.debug('Generated MLLR matrix: %s' % mllr_path)

    # -----------------------------------------------------------------------------

    # Pulled from a run of sphinxtrain/bw
    BW_ARGS = set(['-2passvar',
                    '-abeam',
                    '-accumdir',
                    '-agc',
                    '-agcthresh',
                    '-bbeam',
                    '-cb2mllrfn',
                    '-cepdir',
                    '-cepext',
                    '-ceplen',
                    '-ckptintv',
                    '-cmn',
                    '-cmninit',
                    '-ctlfn',
                    '-diagfull',
                    '-dictfn',
                    '-example',
                    '-fdictfn',
                    '-feat',
                    '-fullsuffixmatch',
                    '-fullvar',
                    '-hmmdir',
                    '-latdir',
                    '-latext',
                    '-lda',
                    '-ldadim',
                    '-lsnfn',
                    '-lw',
                    '-maxuttlen',
                    '-meanfn',
                    '-meanreest',
                    '-mixwfn',
                    '-mixwreest',
                    '-mllrmat',
                    '-mmie',
                    '-mmie_type',
                    '-moddeffn',
                    '-mwfloor',
                    '-npart',
                    '-nskip',
                    '-outphsegdir',
                    '-outputfullpath',
                    '-part',
                    '-pdumpdir',
                    '-phsegdir',
                    '-phsegext',
                    '-runlen',
                    '-sentdir',
                    '-sentext',
                    '-spthresh',
                    '-svspec',
                    '-timing',
                    '-tmatfn',
                    '-tmatreest',
                    '-topn',
                    '-tpfloor',
                    '-ts2cbfn',
                    '-varfloor',
                    '-varfn',
                    '-varnorm',
                    '-varreest',
                    '-viterbi'])
