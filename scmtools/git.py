from reviewboard.diffviewer.parser import \
    DiffParser, DiffParserError, File
    def parse(self):
        """
        Parses the diff, returning a list of File objects representing each
        file in the diff.
        """
        self.files = []
        i = 0
        while i < len(self.lines):
            (i, file) = self._parse_diff(i)
            if file:
                self.files.append(file)
        return self.files

    def _parse_diff(self, i):
        """
        Parses out one file from a Git diff
        """
        if self.lines[i].startswith("diff --git"):
            # First check if it is a new file with no content, then skip
            try:
                if self.lines[i + 1].startswith("new file mode") and \
                        self.lines[i + 3].startswith("diff --git"):
                    i += 3
                    return i, None
            except IndexError, x:
                # This means this is the only bit left in the file
                i += 3
                return i, None

            # Now we check if it is just a file mode change and no content
            try:
                if self.lines[i + 1].startswith("old mode") and \
                        self.lines[i + 3].startswith("diff --git"):
                    i += 3
                    return i, None
            except IndexError, x:
                # This means this is the only bit left in the file
                i += 3
                return i, None

            # Now we have a diff we are going to use so get the filenames + commits
            file = File()
            file.data = self.lines[i] + "\n"
            file.binary = False
            diffLine = self.lines[i].split()
                # Need to remove the "a/" and "b/" prefix
                file.origFile = diffLine[-2][2:]
                file.newFile = diffLine[-1][2:]
                    i)
            i += 1

            # We have no use for recording this info so skip it
            if self.lines[i].startswith("new file mode") \
               or self.lines[i].startswith("deleted file mode"):
                i += 1
            elif self.lines[i].startswith("old mode") \
                 and self.lines[i + 1].startswith("new mode"):
                i += 2

            # Get the revision info
            if i < len(self.lines) and self.lines[i].startswith("index "):
                indexRange = self.lines[i].split(None, 2)[1]
                file.origInfo, file.newInfo = indexRange.split("..")
                if self.pre_creation_regexp.match(file.origInfo):
                    file.origInfo = PRE_CREATION
                i += 1

            # Get the changes
            while i < len(self.lines):
                if self.lines[i].startswith("diff --git"):
                    return i, file

                if self.lines[i].startswith("Binary files") or \
                   self.lines[i].startswith("GIT binary patch"):
                    file.binary = True
                    return i + 1, file

                if i + 1 < len(self.lines) and \
                   (self.lines[i].startswith('--- ') and \
                     self.lines[i + 1].startswith('+++ ')):
                    if self.lines[i].split()[1] == "/dev/null":
                        file.origInfo = PRE_CREATION

                file.data += self.lines[i] + "\n"
                i += 1

            return i, file
        return i, None