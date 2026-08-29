import logging

logger = logging.getLogger("proxiservices.notifications")


class NotificationService:
    """Abstraction d'envoi de notifications (SMS / e-mail).

    Aucun fournisseur SMS/e-mail n'est connecté pour l'instant : le backend
    par défaut se contente de journaliser l'événement. Pour brancher un vrai
    fournisseur une fois les clés API disponibles (ex: Twilio pour le SMS, une
    API d'e-mail transactionnel type Brevo/SendGrid pour l'e-mail), il suffit
    de remplacer le corps de `send_email` / `send_sms` par un appel HTTP réel —
    tous les points d'appel du reste de l'application n'ont pas à changer.
    """

    async def send_email(self, *, to: str, subject: str, body: str) -> None:
        logger.info("NOTIFICATION EMAIL -> %s | %s | %s", to, subject, body)

    async def send_sms(self, *, to: str, message: str) -> None:
        logger.info("NOTIFICATION SMS -> %s | %s", to, message)

    async def notify_user(self, user, *, subject: str, body: str) -> None:
        """Envoie par e-mail (toujours) et par SMS (si un numéro est renseigné)."""
        await self.send_email(to=user.email, subject=subject, body=body)
        if user.phone:
            await self.send_sms(to=user.phone, message=f"{subject} — {body}")


notification_service = NotificationService()
