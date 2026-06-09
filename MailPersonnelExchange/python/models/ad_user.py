from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ADUser:
    display_name: str
    email: str
    sam_account_name: str  # = NIP pour NTLM

    @property
    def initials(self) -> str:
        parts = self.display_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.display_name[:2].upper() if self.display_name else "?"
