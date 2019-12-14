#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
CPU_ARCH="$(uname --m)"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'venv' "${this_dir}/.venv" 'Path to create virtual environment'
DEFINE_string 'download-dir' "${this_dir}/download" 'Directory to cache downloaded files'
DEFINE_string 'build-dir' "${this_dir}/build_${CPU_ARCH}" 'Directory to build dependencies in'
DEFINE_boolean 'system' true 'Install system dependencies'
DEFINE_boolean 'flair' false 'Install flair'
DEFINE_boolean 'precise' false 'Install Mycroft Precise'
DEFINE_boolean 'adapt' false 'Install Mycroft Adapt'
DEFINE_boolean 'google' false 'Install Google Text to Speech'
DEFINE_boolean 'kaldi' false 'Install Kaldi'
DEFINE_boolean 'offline' false "Don't download anything"
DEFINE_integer 'make-threads' 4 'Number of threads to use with make' 'j'
DEFINE_string 'python' 'python3' 'Path to Python executable'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------

set -e

python="${FLAGS_python}"
venv="${FLAGS_venv}"

download_dir="${FLAGS_download_dir}"
mkdir -p "${download_dir}"
echo "Download directory: ${download_dir}"

build_dir="${FLAGS_build_dir}"
mkdir -p "${build_dir}"
echo "Build directory: ${build_dir}"

if [[ "${FLAGS_system}" -eq "${FLAGS_FALSE}" ]]; then
    no_system='true'
fi

if [[ "${FLAGS_flair}" -eq "${FLAGS_FALSE}" ]]; then
    no_flair='true'
fi

if [[ "${FLAGS_precise}" -eq "${FLAGS_FALSE}" ]]; then
    no_precise='true'
fi

if [[ "${FLAGS_adapt}" -eq "${FLAGS_FALSE}" ]]; then
    no_adapt='true'
fi

if [[ "${FLAGS_kaldi}" -eq "${FLAGS_FALSE}" ]]; then
    no_kaldi='true'
fi

if [[ "${FLAGS_google}" -eq "${FLAGS_FALSE}" ]]; then
    no_google='true'
fi

if [[ "${FLAGS_offline}" -eq "${FLAGS_TRUE}" ]]; then
    offline='true'
fi

make_threads="${FLAGS_make_threads}"

# -----------------------------------------------------------------------------

# Create a temporary directory for building stuff
temp_dir="$(mktemp -d)"

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

function maybe_download {
    if [[ ! -s "$2" ]]; then
        if [[ -n "${offline}" ]]; then
            echo "Need to download $1 but offline."
            exit 1
        fi

        mkdir -p "$(dirname "$2")"
        curl -sSfL -o "$2" "$1" || { echo "Can't download $1"; exit 1; }
        echo "$1 => $2"
    fi
}

# -----------------------------------------------------------------------------

echo "Checking required programs"

if [[ ! -n "$(command -v yarn)" ]]; then
    echo "Please install yarn to continue (https://yarnpkg.com)"
    exit 1
fi

# -----------------------------------------------------------------------------

if [[ -z "${no_system}" ]]; then
    echo "Installing system dependencies"

    sudo apt-get update
    sudo apt-get install --no-install-recommends --yes \
         python3 python3-pip python3-venv python3-dev \
         python \
         build-essential autoconf autoconf-archive libtool automake bison \
         sox espeak flite swig portaudio19-dev \
         libatlas-base-dev \
         gfortran \
         sphinxbase-utils sphinxtrain pocketsphinx \
         jq checkinstall unzip xz-utils \
         curl
fi

# -----------------------------------------------------------------------------

echo "Downloading dependencies"

# Python-Pocketsphinx
pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
if [[ ! -s "${pocketsphinx_file}" ]]; then
    pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
    echo "Downloading pocketsphinx (${pocketsphinx_url})"
    maybe_download "${pocketsphinx_url}" "${pocketsphinx_file}"
fi

# OpenFST
openfst_dir="${build_dir}/openfst-1.6.9"
if [[ ! -d "${openfst_dir}/build" ]]; then
    openfst_file="${download_dir}/openfst-1.6.9.tar.gz"

    if [[ ! -s "${openfst_file}" ]]; then
        openfst_url='http://openfst.org/twiki/pub/FST/FstDownload/openfst-1.6.9.tar.gz'
        echo "Downloading openfst (${openfst_url})"
        maybe_download "${openfst_url}" "${openfst_file}"
    fi
fi

# Opengrm
opengrm_dir="${build_dir}/opengrm-ngram-1.3.4"
if [[ ! -d "${opengrm_dir}/build" ]]; then
    opengrm_file="${download_dir}/opengrm-ngram-1.3.4.tar.gz"

    if [[ ! -s "${opengrm_file}" ]]; then
        opengrm_url='http://www.opengrm.org/twiki/pub/GRM/NGramDownload/opengrm-ngram-1.3.4.tar.gz'
        echo "Downloading opengrm (${opengrm_url})"
        maybe_download "${opengrm_url}" "${opengrm_file}"
    fi
fi

# Phonetisaurus
phonetisaurus_dir="${build_dir}/phonetisaurus"
if [[ ! -d "${phonetisaurus_dir}/build" ]]; then
    phonetisaurus_file="${download_dir}/phonetisaurus-2019.tar.gz"

    if [[ ! -s "${phonetisaurus_file}" ]]; then
        phonetisaurus_url='https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019.tar.gz'
        echo "Downloading phonetisaurus (${phonetisaurus_url})"
        maybe_download "${phonetisaurus_url}" "${phonetisaurus_file}"
    fi
fi

# Kaldi
kaldi_dir="${this_dir}/opt/kaldi"
if [[ ! -d "${kaldi_dir}" ]]; then
    install libatlas-base-dev libatlas3-base gfortran
    sudo ldconfig
    kaldi_file="${download_dir}/kaldi-2019.tar.gz"

    if [[ ! -s "${kaldi_file}" ]]; then
        kaldi_url='https://github.com/kaldi-asr/kaldi/archive/master.tar.gz'
        echo "Downloading kaldi (${kaldi_url})"
        maybe_download "${kaldi_url}" "${kaldi_file}"
    fi
fi

# -----------------------------------------------------------------------------

# Re-create virtual environment
echo "Creating virtual environment"
rm -rf "${venv}"
"${python}" -m venv "${venv}"
source "${venv}/bin/activate"
pip3 install wheel setuptools

# -----------------------------------------------------------------------------
# openfst
# http://www.openfst.org
#
# Required to build languag models and do intent recognition.
# -----------------------------------------------------------------------------

if [[ ! -d "${openfst_dir}/build" ]]; then
    echo "Building openfst (${openfst_file})"
    tar -C "${build_dir}" -xf "${openfst_file}" && \
        cd "${openfst_dir}" && \
        ./configure "--prefix=${openfst_dir}/build" \
                    --enable-far \
                    --disable-static \
                    --disable-bin \
                    --enable-shared \
                    --enable-ngram-fsts && \
        make -j "${make_threads}" && \
        make install
fi

# Copy build artifacts into virtual environment
cp -R "${openfst_dir}"/build/include/* "${venv}/include/"
cp -R "${openfst_dir}"/build/lib/*.so* "${venv}/lib/"

# -----------------------------------------------------------------------------
# opengrm
# http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary
# 
# Required to build language models.
# -----------------------------------------------------------------------------

# opengrm
if [[ ! -d "${opengrm_dir}/build" ]]; then
    echo "Building opengrm (${opengrm_file})"
    tar -C "${build_dir}" -xf "${opengrm_file}" && \
        cd "${opengrm_dir}" && \
        CXXFLAGS="-I${venv}/include" LDFLAGS="-L${venv}/lib" ./configure "--prefix=${opengrm_dir}/build" && \
        make -j "${make_threads}" && \
        make install
fi

# Copy build artifacts into virtual environment
cp -R "${opengrm_dir}"/build/bin/* "${venv}/bin/"
cp -R "${opengrm_dir}"/build/include/* "${venv}/include/"
cp -R "${opengrm_dir}"/build/lib/*.so* "${venv}/lib/"

# -----------------------------------------------------------------------------
# phonetisaurus
# https://github.com/AdolfVonKleist/Phonetisaurus
#
# Required to guess word pronunciations.
# -----------------------------------------------------------------------------

if [[ ! -d "${phonetisaurus_dir}/build" ]]; then
    echo "Installing phonetisaurus (${phonetisaurus_file})"
    tar -C "${build_dir}" -xf "${phonetisaurus_file}" && \
        cd "${phonetisaurus_dir}" && \
        ./configure "--prefix=${phonetisaurus_dir}/build" \
                    --with-openfst-includes="${venv}/include" \
                    --with-openfst-libs="${venv}/lib" && \
        make -j "${make_threads}" && \
        make install
fi

# Copy build artifacts into virtual environment
cp -R "${phonetisaurus_dir}"/build/bin/* "${venv}/bin/"

# -----------------------------------------------------------------------------
# kaldi
# https://kaldi-asr.org
#
# Required for speech recognition with Kaldi-based profiles.
# -----------------------------------------------------------------------------

if [[ -z "${no_kaldi}" && ! -f "${kaldi_dir}/src/online2bin/online2-wav-nnet3-latgen-faster" ]]; then
    echo "Installing kaldi (${kaldi_file})"

    # armhf
    if [[ -f '/usr/lib/arm-linux-gnueabihf/libatlas.so' ]]; then
        # Kaldi install doesn't check here, despite in being in ldconfig
        export ATLASLIBDIR='/usr/lib/arm-linux-gnueabihf'
    fi

    # aarch64
    if [[ -f '/usr/lib/aarch64-linux-gnu/libatlas.so' ]]; then
        # Kaldi install doesn't check here, despite in being in ldconfig
        export ATLASLIBDIR='/usr/lib/aarch64-linux-gnu'
    fi

    tar -C "${build_dir}" -xf "${kaldi_file}" && \
        cp "${this_dir}/etc/linux_atlas_aarch64.mk" "${kaldi_dir}/src/makefiles/" && \
        cd "${kaldi_dir}/tools" && \
        make -j "${make_threads}" && \
        cd "${kaldi_dir}/src" && \
        ./configure --shared --mathlib=ATLAS --use-cuda=no && \
            make depend -j "${make_threads}" && \
            make -j "${make_threads}"
fi

# -----------------------------------------------------------------------------
# Python requirements
# -----------------------------------------------------------------------------

echo "Installing Python requirements"

"${python}" -m pip install requests

# pytorch is not available on ARM
case "${CPU_ARCH}" in
    armv7l|arm64v8)
        no_flair="true" ;;
esac

requirements_file="${temp_dir}/requirements.txt"
cp "${this_dir}/requirements.txt" "${requirements_file}"

# Exclude requirements
if [[ -n "${no_flair}" ]]; then
    echo "Excluding flair from virtual environment"
    sed -i '/^flair/d' "${requirements_file}"
fi

if [[ -n "${no_precise}" ]]; then
    echo "Excluding Mycroft Precise from virtual environment"
    sed -i '/^precise-runner/d' "${requirements_file}"
fi

if [[ -n "${no_adapt}" ]]; then
    echo "Excluding Mycroft Adapt from virtual environment"
    sed -i '/^adapt-parser/d' "${requirements_file}"
fi

if [[ -n "${no_google}" ]]; then
    echo "Excluding Google Text to Speech from virtual environment"
    sed -i '/^google-cloud-texttospeech/d' "${requirements_file}"
fi

# Install everything except openfst first
sed -i '/^openfst/d' "${requirements_file}"

"${python}" -m pip install -r "${requirements_file}"

echo "Installing Python openfst wrapper"
"${python}" -m pip install \
            --global-option=build_ext \
            --global-option="-I${venv}/include" \
            --global-option="-L${venv}/lib" \
            -r <(grep '^openfst' "${this_dir}/requirements.txt")

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# https://github.com/cmusphinx/pocketsphinx
#
# Speech to text for most profiles.
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
echo "Installing Python pocketsphinx (${pocketsphinx_file})"

"${python}" -m pip install "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# Snowboy
# https://snowboy.kitt.ai
#
# Wake word system
# -----------------------------------------------------------------------------

case "${CPU_ARCH}" in
    x86_64|armv7l)
        snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
        echo "Installing snowboy (${snowboy_file})"
        "${python}" -m pip install "${snowboy_file}"
        ;;

    *)
        echo "Not installing snowboy (${CPU_ARCH} not supported)"
esac

# -----------------------------------------------------------------------------

echo "Building web interface"
cd "${this_dir}" && yarn build
