from   .base import (Sandbox,
                     SandboxConfig)

import os
from   typing    import List
from   typeguard import typechecked


class SandboxLinux(Sandbox):
    @typechecked
    def __init__(self, config: SandboxConfig, work_dir: str):
        super().__init__(config, work_dir)
        self.nsjail_path = "/usr/bin/nsjail"

    def _build_cmd(self, command_line: List[str]) -> List[str]:
        """
        RETURN: List[str], nsjail invocation with all isolation flags applied,
                           ready to pass to asyncio.create_subprocess_exec.

        Constructs the full nsjail CLI argument list from the current config,
        masking each forbidden binary by bind-mounting /dev/null over it.
        """
        curr_uid = os.getuid()
        curr_gid = os.getgid()

        # COMMAND:
        #    --mode o            Executes target command once then exits.
        # USER:
        #    --user 0            Runs jailed process as root user.
        #    --group 0           Runs jailed process as root group.
        #    --uid_mapping       Maps jail's root UID to host's current UID.
        #    --gid_mapping       Maps jail's root GID to host's current GID.
        # FILE SYSTEM:
        #    --chroot /          Sets the jail's apparent root directory.
        #    -R                  Bind-mounts base filesystem as read-only.
        #    -R /dev/null:{bin}  Masks forbidden binary by bind-mounting
        #                        '/dev/null' over it.
        #    -M                  Bind-mounts working directory as read-write.
        #    --cwd               Sets starting directory inside the jail.
        # RESOURCES:
        #    --rlimit_fsize      Sets max allowed size for files created in jail.
        #    --cgroup_mem_max    Caps maximum RAM usage via cgroups.
        #    --cgroup_pids_max   Caps maximum process/thread count via cgroups.
        #    --time_limit        Enforces hard CPU execution time limit.
        # NETWORK:
        #    --disable_clone_newnet Disables network namespace isolation.
        args = [
            self.nsjail_path,
            "--quiet",
            "--mode",             "o",
            "--uid_mapping",      f"0:{curr_uid}:1",
            "--gid_mapping",      f"0:{curr_gid}:1",
            "--rlimit_fsize",     str(self.config.rsrc_max_file_size_mb),
            "--user",             "0",
            "--group",            "0",
            "--chroot",           "/",
            "-R",                 self.config.fs_root_mount,
            "-M",                 f"{self.work_dir}:{self.work_dir}",
            "--cwd",              str(self.work_dir),
            "--cgroup_mem_max",   str(self.config.rsrc_max_memory_mb * 1024 * 1024),
            "--cgroup_pids_max",  str(self.config.rsrc_max_pids),
            "--time_limit",       str(self.config.rsrc_max_cpu_time_sec),
        ]

        if self.config.ntw_share_host_network:
            args.append("--disable_clone_newnet")
        else:
            if self.config.ntw_disable_loopback:
                args.append("--iface_no_lo")

            if self.config.ntw_macvlan_iface:
                args.extend(["--macvlan_iface", self.config.ntw_macvlan_iface])
                if self.config.ntw_macvlan_ip:
                    args.extend(["--macvlan_vs_ip", self.config.ntw_macvlan_ip])
                if self.config.ntw_macvlan_gw:
                    args.extend(["--macvlan_vs_gw", self.config.ntw_macvlan_gw])

        for bin_path in self.config.fs_forbidden_apps:
            if os.path.exists(bin_path):
                args.extend(["-R", f"/dev/null:{bin_path}"])

        args.append("--")
        args.extend(command_line)
        return args
