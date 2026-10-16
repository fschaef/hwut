#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "Installing hwut: each form from nothing to a green demonstration"
#     features = ["wheel-installs"]
#     choices {
#         wheel { features = ["wheel-installs", "demo-green", "one-version"] }
#         pipx  { features = ["pipx-installs", "demo-green", "one-version"] }
#         deb-debian { features = ["deb-installs", "deb-removes", "demo-green", "one-version"] }
#         deb-ubuntu { features = ["deb-installs", "deb-removes", "demo-green", "one-version"] }
#         image      { features = ["image-runs", "image-owner", "demo-green", "one-version"] }
#     }
#     tolerance { eq_pattern = ["[0-9]+\\.[0-9]+ \\[sec\\]"] }
#     caps { timeout_sec = 900 }
# }
#
# ---------------------------------------------------------------------------
#
# EACH FORM, FROM NOTHING (adm/WORK/spec/24, section 4): built from this
# tree by 'adm/packaging/build.py', installed where nothing of hwut stands,
# and asked what the book shows -- the version, the faces on PATH,
# 'hwut.help', and the demonstration's RESULTS line.
#
#     wheel   a fresh virtual environment, 'pip install <wheel>'
#     pipx    'pipx install <wheel>', PATH holding pipx's directory and
#             the system's alone
#     deb-debian, deb-ubuntu
#             a fresh container of Debian stable ('debian:13') or Ubuntu
#             LTS ('ubuntu:24.04'): 'apt-get install ./hwut_<v>_all.deb',
#             the requirements from the distribution; asked; then 'apt-get
#             remove hwut', and every file named '*hwut*' left counted.
#             Podman, or docker; the distribution's mirrors reached.
#     image   'build.py image': the runtime image, then everything from
#             outside -- nothing of hwut on the host: 'hwut.help', the
#             demonstration written and run in the mounted directory, and
#             the owner of what the run wrote there
#
# NOT IN THE CENSUS: it fetches the dependencies from PyPI, and the later
# forms need a container engine. The page carries the label 'meta'
# ('hwut-root.labels'), silent unless a wish names a label:
#
#     hwut.run -l meta -k packaging
#
# A MISSING TOOL IS A MISSING PRECONDITION, said as one: the choice goes
# red, never green unasked.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
HWUT=$(cd "$HERE/../../.." && pwd)
unset NO_COLOR CI PYTHONPATH

WORK=$(mktemp -d /tmp/hwut-install.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

need() {                #  <program>: said and ended where it is absent
    command -v "$1" > /dev/null 2>&1 && return 0
    echo "MISSING PRECONDITION: '$1' is not on PATH"
    echo "<hwut-end>"
    exit 0
}

wheel_built() {         #  the wheel's path, built into $WORK/dist
    python3 "$HWUT/adm/packaging/build.py" wheel "$WORK/dist" \
        | sed -n 's/^BUILT: //p'
}

asked() {               #  what the book shows, by the faces on PATH
    echo "version:      $(hwut.about --version)"
    echo "faces:        $(compgen -c hwut | grep -E '^hwut(\.|$)' | sort -u | wc -l) on PATH"
    echo "hwut.dev.*:   $(compgen -c hwut.dev. | wc -l) on PATH"
    hwut.demo.python "$WORK/demo" > /dev/null
    cd "$WORK/demo/TEST"
    hwut.help > "$WORK/help.txt" 2>&1
    echo "hwut.help:    status $?, $(head -1 "$WORK/help.txt")"
    hwut --plain 2>&1 | grep '^RESULTS'
}

#  INSIDE A FRESH CONTAINER: the package installed, asked, removed.
inside() {
    export DEBIAN_FRONTEND=noninteractive WORK=/tmp/asked
    mkdir -p "$WORK"
    apt-get update -qq > /dev/null 2>&1
    apt-get install -y -qq "${HWUT_DEB:-/work/dist/hwut.deb}" > "$WORK/apt.txt" 2>&1
    echo "installed:    status $?, hwut_<version>_all.deb"
    (asked)
    apt-get remove -y -qq hwut > "$WORK/apt.txt" 2>&1
    echo "removed:      status $?"
    rm -rf "$WORK"
    left=$(find / -xdev \( -path /proc -o -path /work -o -path /tmp \) -prune \
                -o -iname '*hwut*' -print 2>/dev/null | wc -l)
    echo "left behind:  $left file(s) named '*hwut*'"
}

in_container() {        #  <image>: the deb built, installed in a fresh <image>
    engine_answering
    mkdir -p "$WORK/dist"
    DEB=$(python3 "$HWUT/adm/packaging/build.py" deb "$WORK/dist" \
          | sed -n 's/^BUILT: //p')
    mv "$DEB" "$WORK/dist/hwut.deb"
    { declare -f asked inside; echo inside; } > "$WORK/inside.sh"
    "$ENGINE" run --rm -v "$WORK":/work:Z "$1" bash /work/inside.sh
}

engine_answering() {    #  the engine that answers, or the precondition said
    ENGINE=$(command -v podman || command -v docker)
    if [ -z "$ENGINE" ] || ! "$ENGINE" info > /dev/null 2>&1; then
        echo "MISSING PRECONDITION: no container engine answers (podman, docker)"
        echo "<hwut-end>"
        exit 0
    fi
}

image_asked() {         #  the image from outside, the host holding no hwut
    engine_answering
    TAG=$(python3 "$HWUT/adm/packaging/build.py" image "$WORK/context" \
          | sed -n 's/^BUILT: //p')
    echo "built:        $(echo "$TAG" | sed 's/:[0-9.]*$/:<version>/')"
    #  THE CALLER OWNS WHAT THE RUN WRITES: podman maps the caller in,
    #  docker is told the caller.
    case "$ENGINE" in
        *podman) AS="--userns=keep-id"; MOUNT="$WORK/mounted:/work:Z" ;;
        *)       AS="--user=$(id -u):$(id -g)"; MOUNT="$WORK/mounted:/work" ;;
    esac
    mkdir -p "$WORK/mounted"
    run() { "$ENGINE" run --rm "$AS" -v "$MOUNT" -w /work "$TAG" "$@"; }
    echo "version:      $(run hwut.about --version)"
    echo "faces:        $(run bash -c 'compgen -c hwut | grep -E "^hwut(\.|$)" | sort -u | wc -l') in the image"
    run hwut.help > "$WORK/help.txt" 2>&1
    echo "hwut.help:    status $?, $(head -1 "$WORK/help.txt")"
    run hwut.demo.python /work/demo > /dev/null
    run bash -c 'cd /work/demo/TEST && hwut --plain' 2>&1 | grep '^RESULTS'
    foreign=$(find "$WORK/mounted" ! -user "$(id -u)" | wc -l)
    echo "written:      $(find "$WORK/mounted" | wc -l | sed 's/[0-9]*/<n>/') entries, $foreign not the caller's"
}

case "$1" in
    --hwut-info)
        echo "Installing hwut: each form from nothing to a green demonstration;"
        echo "CHOICES: wheel, pipx, deb-debian, deb-ubuntu, image;"
        exit 0 ;;
    wheel)
        need python3
        WHEEL=$(wheel_built)
        python3 -m venv "$WORK/venv"
        "$WORK/venv/bin/pip" install --quiet "$WHEEL" > "$WORK/pip.txt" 2>&1
        echo "installed:    status $?, $(basename "$WHEEL")"
        PATH="$WORK/venv/bin:/usr/bin:/bin" asked ;;
    pipx)
        need python3
        need pipx
        WHEEL=$(wheel_built)
        export PIPX_HOME="$WORK/pipx" PIPX_BIN_DIR="$WORK/pipx-bin"
        pipx install "$WHEEL" > "$WORK/pipx.txt" 2>&1
        echo "installed:    status $?, $(basename "$WHEEL")"
        PATH="$WORK/pipx-bin:/usr/bin:/bin" asked ;;
    deb-debian)
        need python3; need dpkg-deb
        in_container docker.io/library/debian:13 ;;
    deb-ubuntu)
        need python3; need dpkg-deb
        in_container docker.io/library/ubuntu:24.04 ;;
    image)
        need python3; need dpkg-deb
        image_asked ;;
    *)
        echo "choices: wheel, pipx, deb-debian, deb-ubuntu, image"; exit 1 ;;
esac
echo "<hwut-end>"
