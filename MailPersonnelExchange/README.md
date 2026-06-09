# MailPersonnelExchange

Prototype Windows pour consulter une boîte personnelle Exchange local depuis une session publique.

## Pré-requis

- Windows 10/11
- .NET 8 SDK
- Accès réseau au serveur Exchange local
- EWS activé sur Exchange
- URL EWS, par exemple : https://mail.domaine.ch/EWS/Exchange.asmx

## Lancement

1. Ouvrir `MailPersonnelExchange.sln` dans Visual Studio 2022.
2. Restaurer les packages NuGet.
3. Compiler et lancer.

## Sécurité

- Le mot de passe n'est pas sauvegardé.
- Il est uniquement utilisé en mémoire pendant la session.
- Le champ mot de passe est vidé à la déconnexion.
- Prévoir une fermeture automatique après inactivité pour une vraie mise en production.

## Fonctions MVP

- Connexion Exchange EWS avec utilisateur AD/NIP + domaine + mot de passe.
- Affichage des 50 derniers mails de la boîte de réception.
- Lecture du contenu texte.
- Réponse à un mail.
- Nouveau mail.
- Déconnexion.
