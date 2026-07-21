#!/bin/bash
#
# setup_deploy.sh -- verify/create the directories and symlinks required
# for tide station operation, then copy tracked .html/.txt/.cgi files
# from this repo checkout to their live destinations.
#
# Run from the repo checkout directory (~/bin/tidegauge). Safe to re-run
# any time -- every step checks current state before acting, and nothing
# is overwritten blindly.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CGI_DEST="/usr/lib/cgi-bin"
HTML_DEST="/var/www/html"

echo "Repo directory: $REPO_DIR"
echo "=================================================="

# --------------------------------------------------------------------
# 1. Directories
# --------------------------------------------------------------------
echo ""
echo "--- Checking directories ---"

ensure_dir() {
    local dir="$1" owner="$2" mode="$3"
    if [ -d "$dir" ]; then
        echo "OK (exists): $dir"
    else
        echo "MISSING -- creating: $dir"
        sudo mkdir -p "$dir"
    fi
    sudo chown "$owner" "$dir"
    sudo chmod "$mode" "$dir"
}

ensure_dir "$HTML_DEST/mailspool"        tide:tide 770
ensure_dir "$HTML_DEST/mailspool/failed" tide:tide 700

# --------------------------------------------------------------------
# 2. Symlinks
# --------------------------------------------------------------------
echo ""
echo "--- Checking symlinks ---"

ensure_symlink() {
    local target="$1" link="$2"

    if [ ! -e "$target" ]; then
        echo "WARNING: symlink target does not exist, skipping: $target"
        return
    fi

    if [ -L "$link" ]; then
        # Already a symlink -- check it points at the right place
        current_target="$(readlink -f "$link")"
        real_target="$(readlink -f "$target")"
        if [ "$current_target" == "$real_target" ]; then
            echo "OK (correct symlink): $link -> $target"
            return
        else
            echo "WRONG TARGET -- relinking: $link (was -> $current_target)"
            sudo rm -f "$link"
            sudo ln -s "$target" "$link"
        fi
    elif [ -e "$link" ]; then
        # A real file sits at the link path -- do NOT blindly overwrite.
        # This project has been burned before by deleting what looked
        # like a duplicate but wasn't (encryption keys, tide.env).
        if cmp -s "$target" "$link"; then
            echo "REAL FILE at link path, but content matches target exactly -- safe to replace: $link"
            sudo rm -f "$link"
            sudo ln -s "$target" "$link"
        else
            echo "REAL FILE at link path with DIFFERENT content -- NOT touching, check manually: $link"
            return
        fi
    else
        echo "MISSING -- creating: $link -> $target"
        sudo ln -s "$target" "$link"
    fi

    sudo chown -h tide:tide "$link"
}

ensure_symlink "$REPO_DIR/tidecrypto.py" "$CGI_DEST/tidecrypto.py"
ensure_symlink "$REPO_DIR/tideplot.py"   "$CGI_DEST/tideplot.cgi"
ensure_symlink "$REPO_DIR/tide.env"      "$HTML_DEST/tide.env"

# --------------------------------------------------------------------
# 3. Copy tracked files to their destinations
# --------------------------------------------------------------------
echo ""
echo "--- Copying tracked files ---"

cd "$REPO_DIR"

copy_tracked() {
    local pattern="$1" dest="$2" perms="$3"
    git ls-files "$pattern" | while read -r f; do
        echo "  $f -> $dest/"
        sudo cp "$f" "$dest/"
        sudo chmod "$perms" "$dest/$(basename "$f")"
    done
}

echo "CGI files -> $CGI_DEST"
copy_tracked '*.cgi' "$CGI_DEST" 755

echo "HTML files -> $HTML_DEST"
copy_tracked '*.html' "$HTML_DEST" 644

echo "TXT files -> $HTML_DEST"
copy_tracked '*.txt' "$HTML_DEST" 644

echo "PDF files -> $HTML_DEST"
copy_tracked '*.pdf' "$HTML_DEST" 644

echo ""
echo "=================================================="
echo "Done."