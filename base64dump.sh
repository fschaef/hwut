git ls-tree -r --name-only HEAD | grep -v '^vut/doc/logo/' | grep -v PHILO | grep -v '\.7z$'   | tar cf - -T - | xz -9e | base64 -w 76
