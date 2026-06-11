import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from qt_material import apply_stylesheet

from services.ews_service import EwsService
from views.login_window import LoginWindow
from views.main_window import MainWindow, _THEME_EXTRA


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Promed Messagerie")
    app.setOrganizationName("Promed")

    apply_stylesheet(app, theme="light_blue.xml", extra=_THEME_EXTRA)

    login = LoginWindow()
    login.show()

    _wins: list[MainWindow] = []

    def on_authenticated(ews: EwsService, email: str, ad_users: list) -> None:
        login.hide()
        win = MainWindow(ews, email, ad_users)
        _wins.clear()
        _wins.append(win)
        win.logout_requested.connect(on_logout)
        win.show()

    def on_logout() -> None:
        if _wins:
            _wins[0].close()
            _wins.clear()
        login.show()

    login.authenticated.connect(on_authenticated)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
