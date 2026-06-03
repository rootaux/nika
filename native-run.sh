#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${NIKA_VENV_DIR:-${SCRIPT_DIR}/.venv}"
NATIVE_CONFIG_PATH="${NIKA_NATIVE_CONFIG:-${SCRIPT_DIR}/config/native-crtConfig.yml}"
BOOTSTRAP_SCRIPT="${SCRIPT_DIR}/native-build.sh"
ENV_FILE="${SCRIPT_DIR}/.native-env"
PYTHON_BIN="${VENV_DIR}/bin/python"

usage() {
    cat <<EOF
Usage:
  ./native-run.sh [--bootstrap] --path /absolute/path/to/source [--output report.html] [other nika args]

Options:
  --bootstrap   Force rerunning native-build.sh before execution.
  -h, --help    Show this help.
EOF
}

needs_bootstrap() {
    [[ ! -x "${BOOTSTRAP_SCRIPT}" ]] && return 0
    [[ ! -x "${PYTHON_BIN}" ]] && return 0
    [[ ! -f "${NATIVE_CONFIG_PATH}" ]] && return 0
    [[ ! -f "${ENV_FILE}" ]] && return 0
    return 1
}

run_bootstrap() {
    "${BOOTSTRAP_SCRIPT}"
}

main() {
    local force_bootstrap=0
    local args=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --bootstrap)
                force_bootstrap=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done

    if [[ "${force_bootstrap}" == "1" ]] || needs_bootstrap; then
        run_bootstrap
    fi

    [[ -x "${PYTHON_BIN}" ]] || {
        echo "native Python environment is missing; rerun ./native-build.sh" >&2
        exit 1
    }
    [[ -f "${NATIVE_CONFIG_PATH}" ]] || {
        echo "native config is missing; rerun ./native-build.sh" >&2
        exit 1
    }

    export NIKA_NATIVE_CONFIG="${NATIVE_CONFIG_PATH}"
    if [[ -f "${ENV_FILE}" ]]; then
        # shellcheck disable=SC1090
        source "${ENV_FILE}"
    fi

    exec "${PYTHON_BIN}" "${SCRIPT_DIR}/main.py" --config "${NATIVE_CONFIG_PATH}" "${args[@]}"
}

main "$@"