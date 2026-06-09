import sys
from getopt import GetoptError

import ipdb

from chatdbg.chatdbg_pdb import ChatDBG
from chatdbg.util.config import chatdbg_config
from chatdbg.util.help import print_help


def main() -> None:
    if "--analyze" in sys.argv:
        idx = sys.argv.index("--analyze")
        if idx + 1 >= len(sys.argv):
            print("chatdbg: --analyze requires a crash log file argument")
            print("Usage: chatdbg --analyze <crash_log_file> [--repo <dir>] [--model MODEL]")
            sys.exit(1)
        log_file = sys.argv[idx + 1]
        remaining = sys.argv[1:idx] + sys.argv[idx + 2:]

        repo_path = None
        if "--repo" in remaining:
            repo_idx = remaining.index("--repo")
            if repo_idx + 1 < len(remaining):
                repo_path = remaining[repo_idx + 1]
                remaining = remaining[:repo_idx] + remaining[repo_idx + 2:]
            else:
                print("chatdbg: --repo requires a directory argument")
                sys.exit(1)

        chatdbg_config.parse_user_flags(remaining)
        from chatdbg.postmortem.analyze import analyze_crash_log

        analyze_crash_log(log_file, repo_path=repo_path)
        return

    ipdb.__main__._get_debugger_cls = lambda: ChatDBG

    args = chatdbg_config.parse_user_flags(sys.argv[1:])

    if "-h" in args or "--help" in args:
        print_help()

    sys.argv = [sys.argv[0]] + args

    try:
        ipdb.__main__.main()
    except GetoptError as e:
        print(f"Unrecognized option: {e.opt}\n")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
