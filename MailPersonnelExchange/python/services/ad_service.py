from __future__ import annotations

from models.ad_user import ADUser


class ADService:
    """
    Queries Active Directory using Windows ADSI (ADsDSOObject OLE DB provider).
    Uses the current Windows session — no credentials needed.
    """

    def query_users(self, ldap_url: str, base_dn: str) -> list[ADUser]:
        import win32com.client

        # Extract hostname from ldap://hostname
        server = ldap_url.removeprefix("ldaps://").removeprefix("ldap://").rstrip("/")

        conn = win32com.client.Dispatch("ADODB.Connection")
        conn.Provider = "ADsDSOObject"
        conn.Open("ADs Provider")

        cmd = win32com.client.Dispatch("ADODB.Command")
        cmd.ActiveConnection = conn

        # LDAP dialect: <LDAP://server/base_dn>;filter;attributes;scope
        cmd.CommandText = (
            f"<LDAP://{server}/{base_dn}>;"
            "(&(objectClass=user)(mail=*)"
            "(!(userAccountControl:1.2.840.113556.1.4.803:=2)));"
            "displayName,mail,sAMAccountName;"
            "subtree"
        )
        cmd.Properties("Page Size").Value = 1000

        rs, _ = cmd.Execute()

        users: list[ADUser] = []
        while not rs.EOF:
            name = str(rs.Fields("displayName").Value or "").strip()
            mail = str(rs.Fields("mail").Value or "").strip()
            sam  = str(rs.Fields("sAMAccountName").Value or "").strip()
            if name and mail:
                users.append(ADUser(display_name=name, email=mail, sam_account_name=sam))
            rs.MoveNext()

        conn.Close()
        return sorted(users, key=lambda u: u.display_name.lower())
