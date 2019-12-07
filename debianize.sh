#!/usr/bin/env bash
rhasspy_version="2.4.8"

this_dir="$( cd "$( dirname "$0" )" && pwd )"

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'architecture' '' 'Debian architecture'
DEFINE_string 'version' "${rhasspy_version}" 'Package version'
DEFINE_boolean 'package' true 'Create debian package (.deb)'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------

export architecture="${FLAGS_architecture}"
version="${FLAGS_version}"
debian_dir="${this_dir}/debian"

set -e

if [[ -z "${architecture}" ]]; then
    # Guess architecture
    architecture="$(dpkg-architecture | grep 'DEB_BUILD_ARCH=' | sed 's/^[^=]\+=//')"
fi

# -----------------------------------------------------------------------------
# Activate virtual environment
# -----------------------------------------------------------------------------

venv="${this_dir}/.venv"

if [[ ! -d "${venv}" ]]; then
    echo "Missing virtual environment at ${venv}"
    echo "Did you run create-venv.sh?"
    exit 1
fi

cd "${this_dir}"
source "${venv}/bin/activate"

if [[ -z "$(which pyinstaller)" ]]; then
    echo "Missing PyInstaller"
    exit 1
fi

# -----------------------------------------------------------------------------
# Run PyInstaller
# -----------------------------------------------------------------------------

echo "Running PyInstaller"
package_name="rhasspy-server_${version}_${architecture}"
package_dir="${debian_dir}/${package_name}"
output_dir="${package_dir}/usr/lib/rhasspy"
share_dir="${package_dir}/usr/share/rhasspy"

pyinstaller\
    -y \
    --workpath "pyinstaller/build" \
    --distpath "${output_dir}" \
    "${this_dir}/rhasspy.spec"

# Remove all symbols (Liantian warning)
strip --strip-all "${output_dir}/rhasspy"/*.so* || true

# Remove executable bit from shared libs (Lintian warning)
chmod -x "${output_dir}/rhasspy"/*.so* || true

# -----------------------------------------------------------------------------
# Copy Rhasspy
# -----------------------------------------------------------------------------

# Profiles
mkdir -p "${output_dir}/profiles"
rsync -av \
      --delete \
      --exclude 'acoustic_model' \
      --exclude 'download' \
      --exclude 'flair' \
      --exclude 'base_dictionary.txt' \
      --exclude 'base_language_model.txt' \
      --exclude 'g2p.fst' \
      --exclude 'HCLG.fst' \
      --exclude 'final.mdl' \
      --exclude '*.umdl' \
      "${this_dir}/profiles/" \
      "${output_dir}/profiles/"

# Sounds
mkdir -p "${output_dir}/etc/wav"
rsync -av \
      --delete \
      "${this_dir}/etc/wav/" \
      "${output_dir}/etc/wav/"

# Web
mkdir -p "${output_dir}/dist"
rsync -av \
      --delete \
      "${this_dir}/dist/" \
      "${output_dir}/dist/"

# Documentation
mkdocs build
mkdir -p "${share_dir}/docs"
rsync -av \
      --delete \
      "${this_dir}/site/" \
      "${share_dir}/docs/"

# Source code
mkdir -p "${share_dir}/src"
rsync -av \
      --delete \
      --exclude '.mypy_cache' \
      --exclude '__pycache__' \
      "${this_dir}/rhasspy/" \
      "${share_dir}/src/rhasspy/"

cp "${this_dir}/app.py" "${share_dir}/src/"

# -----------------------------------------------------------------------------
# Copy Kaldi
# -----------------------------------------------------------------------------

echo "Copying Kaldi"
kaldi_src="${venv}/kaldi"
if [[ ! -d "${kaldi_src}" ]]; then
    echo "Missing Kaldi at ${kaldi_src}"
    exit 1
fi

kaldi_dest="${output_dir}/kaldi"
mkdir -p "${kaldi_dest}"
rsync -av --delete "${kaldi_src}/" "${kaldi_dest}/"

# Avoid link recursion
rm -f "${kaldi_dest}/egs/wsj/s5/utils/utils"

# Turn duplicate .so files into symbolic links
function fix_library_links() {
    lib_dir="$1"

    for lib in "${lib_dir}"/*.so; do
        lib_base="$(basename ${lib})"
        for lib_link in "${lib_dir}/${lib_base}".*; do
            rm -f "${lib_link}"
            ln -s "${lib_base}" "${lib_link}"
        done
    done
}

fix_library_links "${kaldi_dest}/tools/openfst/lib"

# -----------------------------------------------------------------------------
# Create Debian package
# -----------------------------------------------------------------------------

echo "Creating Debian package"
mkdir -p "${package_dir}/DEBIAN"
cat "${debian_dir}/DEBIAN/control" | \
    envsubst > "${package_dir}/DEBIAN/control"

mkdir -p "${package_dir}/usr/bin"
cp "${debian_dir}/bin/rhasspy-server" "${package_dir}/usr/bin/"

if [[ "${FLAGS_package}" -eq "${FLAGS_TRUE}" ]]; then
    # Actually build the package
    cd 'debian' && fakeroot dpkg --build "${package_name}"
fi
