#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'venv' "${this_dir}/.venv" 'Path to create virtual environment'
DEFINE_string 'download-dir' "${this_dir}/download" 'Directory to cache downloaded files'
DEFINE_boolean 'system' true 'Install system dependencies'
DEFINE_boolean 'flair' false 'Install flair'
DEFINE_boolean 'precise' false 'Install Mycroft Precise'
DEFINE_boolean 'adapt' true 'Install Mycroft Adapt'
DEFINE_boolean 'google' false 'Install Google Text to Speech'
DEFINE_boolean 'kaldi' true 'Install Kaldi'
DEFINE_boolean 'offline' false "Don't download anything"
DEFINE_integer 'make-threads' 4 'Number of threads to use with make' 'j'
DEFINE_string 'python' '' 'Path to Python executable'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------

set -e

venv="${FLAGS_venv}"
download_dir="${FLAGS_download_dir}"
mkdir -p "${download_dir}"

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

# -----------------------------------------------------------------------------

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
# Debian dependencies
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
         curl \
         lame
fi

# -----------------------------------------------------------------------------
# Python >= 3.6
# -----------------------------------------------------------------------------

if [[ -z "${FLAGS_python}" ]]; then
    # Auto-detect Python
    if [[ -n "$(command -v python3.8)" ]]; then
        PYTHON='python3.8'
    elif [[ -n "$(command -v python3.7)" ]]; then
        PYTHON='python3.7'
    elif [[ -n "$(command -v python3.6)" ]]; then
        PYTHON='python3.6'
    else
        echo "Installing Python 3.6 from source. This is going to take a LONG time."
        sudo apt-get install --no-install-recommends --yes \
             tk-dev libncurses5-dev libncursesw5-dev \
             libreadline6-dev libdb5.3-dev libgdbm-dev \
             libsqlite3-dev libssl-dev libbz2-dev \
             libexpat1-dev liblzma-dev zlib1g-dev

        python_file="${download_dir}/Python-3.6.8.tar.xz"
        python_url='https://www.python.org/ftp/python/3.6.8/Python-3.6.8.tar.xz'
        maybe_download "${python_url}" "${python_file}"

        tar -C "${temp_dir}" -xf "${python_file}"
        cd "${temp_dir}/Python-3.6.8" && \
            ./configure && \
            make -j "${make_threads}" && \
            sudo make altinstall

        PYTHON='python3.6'
    fi
else
    # User-provided Python
    PYTHON="${FLAGS_python}"
fi

# -----------------------------------------------------------------------------
# Download dependencies
# -----------------------------------------------------------------------------

# CPU architecture
CPU_ARCH="$(uname --m)"
case "${CPU_ARCH}" in
    x86_64)
        FRIENDLY_ARCH=amd64
        ;;

    armv7l)
        FRIENDLY_ARCH=armhf
        ;;

    arm64v8)
        FRIENDLY_ARCH=aarch64
        ;;

    *)
        FRIENDLY_ARCH="${CPU_ARCH}"
        ;;
esac

echo "Downloading dependencies"
download_args=()
if [[ -n "${offline}" ]]; then
    download_args+=('--offline')
fi

if [[ -n "${no_precise}" ]]; then
    download_args+=('--noprecise')
fi

if [[ -n "${no_kaldi}" ]]; then
    download_args+=('--nokaldi')
fi

bash download-dependencies.sh "${download_args[@]}"

# -----------------------------------------------------------------------------
# Virtual environment
# -----------------------------------------------------------------------------

cd "${this_dir}"

echo "${venv}"

if [[ -d "${venv}" ]]; then
    echo "Removing existing virtual environment"
    rm -rf "${venv}"
fi

echo "Creating new virtual environment"
mkdir -p "${venv}"
"${PYTHON}" -m venv "${venv}"

# Extract Rhasspy tools
rhasspy_tools_file="${download_dir}/rhasspy-tools_${FRIENDLY_ARCH}.tar.gz"
echo "Extracting tools (${rhasspy_tools_file})"
tar -C "${venv}" -xf "${rhasspy_tools_file}"

# Force .venv/lib to be used
export LD_LIBRARY_PATH="${venv}/lib:${LD_LIBRARY_PATH}"

# shellcheck source=/dev/null
source "${venv}/bin/activate"

echo "Upgrading pip"
"${PYTHON}" -m pip install --upgrade pip

echo "Installing Python requirements"
"${PYTHON}" -m pip install wheel setuptools
"${PYTHON}" -m pip install requests

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
python3 -m pip install -r "${requirements_file}"

# Install Python openfst wrapper
"${PYTHON}" -m pip install \
            --global-option=build_ext \
            --global-option="-I${venv}/include" \
            --global-option="-L${venv}/lib" \
            -r <(grep '^openfst' "${this_dir}/requirements.txt")

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
"${PYTHON}" -m pip install "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

case "${CPU_ARCH}" in
    x86_64|armv7l)
        snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
        "${PYTHON}" -m pip install "${snowboy_file}"
        ;;

    *)
        echo "Not installing snowboy (${CPU_ARCH} not supported)"
esac

# -----------------------------------------------------------------------------
# Mycroft Precise
# -----------------------------------------------------------------------------

if [[ -z "${no_precise}" && -z "$(command -v precise-engine)" ]]; then
    case "${CPU_ARCH}" in
        x86_64|armv7l)
            echo "Installing Mycroft Precise"
            precise_file="${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
            precise_install="${venv}/lib"
            tar -C "${precise_install}" -xf "${precise_file}"
            ln -s "${precise_install}/precise-engine/precise-engine" "${venv}/bin/precise-engine"
            ;;

        *)
            echo "Not installing Mycroft Precise (${CPU_ARCH} not supported)"
    esac
fi

# -----------------------------------------------------------------------------
# Kaldi
# -----------------------------------------------------------------------------

if [[ -z "${no_kaldi}" ]]; then
    kaldi_file="${download_dir}/kaldi_${FRIENDLY_ARCH}.tar.gz"
    echo "Installing Kaldi (${kaldi_file})"
    mkdir -p "${this_dir}/opt"
    tar -C "${this_dir}/opt" -xf "${kaldi_file}"
fi

# -----------------------------------------------------------------------------
# Web Interface
# -----------------------------------------------------------------------------

rhasspy_web_file="${download_dir}/rhasspy-web-dist.tar.gz"
echo "Extracting web interface (${rhasspy_web_file})"
tar -C "${this_dir}" -xf "${rhasspy_web_file}"

# -----------------------------------------------------------------------------

echo "Done"
