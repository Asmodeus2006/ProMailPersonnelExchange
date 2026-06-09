using Microsoft.Exchange.WebServices.Data;
using System;
using System.Drawing;
using Task = System.Threading.Tasks.Task;
using System.Windows.Forms;

namespace MailPersonnelExchange;

public class ComposeForm : Form
{
    private static readonly Color AppBack = Color.FromArgb(245, 247, 250);
    private static readonly Color PanelBack = Color.White;
    private static readonly Color BorderColor = Color.FromArgb(219, 226, 236);
    private static readonly Color Primary = Color.FromArgb(20, 93, 160);
    private static readonly Color PrimaryDark = Color.FromArgb(13, 69, 121);
    private static readonly Color TextMain = Color.FromArgb(31, 41, 55);
    private static readonly Color TextMuted = Color.FromArgb(91, 105, 123);

    private readonly ExchangeService service;
    private readonly EmailMessage? replyTo;
    private readonly TextBox txtTo = CreateTextBox("destinataire@promed-lab.ch");
    private readonly TextBox txtSubject = CreateTextBox("Sujet");
    private readonly RichTextBox txtMessage = new();
    private readonly Button btnSend = CreateButton("Envoyer", true);
    private readonly Button btnCancel = CreateButton("Annuler");
    private readonly Label lblTitle = new();
    private readonly Label lblHint = new();

    public ComposeForm(ExchangeService service, EmailMessage? replyTo)
    {
        this.service = service;
        this.replyTo = replyTo;

        Text = replyTo == null ? "Nouveau mail" : "Repondre";
        MinimumSize = new Size(760, 560);
        Size = new Size(860, 650);
        StartPosition = FormStartPosition.CenterParent;
        Font = new Font("Segoe UI", 10F);
        BackColor = AppBack;

        BuildLayout();

        if (replyTo != null)
        {
            txtTo.Enabled = false;
            txtTo.Text = "Reponse au message selectionne";
            txtSubject.Text = "RE: " + replyTo.Subject;
            lblTitle.Text = "Repondre au message";
            lblHint.Text = "Ton texte sera ajoute en haut de la reponse.";
        }
        else
        {
            lblTitle.Text = "Nouveau mail";
            lblHint.Text = "Redige un message clair, puis envoie-le via Exchange.";
        }

        btnSend.Click += async (_, _) => await SendAsync();
        btnCancel.Click += (_, _) => Close();
    }

    private void BuildLayout()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = AppBack,
            ColumnCount = 1,
            RowCount = 1,
            Padding = new Padding(18)
        };

        var shell = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = PanelBack,
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(18)
        };

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 5,
            ColumnCount = 1
        };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 58));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 58));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 58));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));

        var header = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1 };
        header.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        header.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
        lblTitle.Dock = DockStyle.Fill;
        lblTitle.Font = new Font("Segoe UI Semibold", 15F);
        lblTitle.ForeColor = TextMain;
        lblHint.Dock = DockStyle.Fill;
        lblHint.ForeColor = TextMuted;
        header.Controls.Add(lblTitle, 0, 0);
        header.Controls.Add(lblHint, 0, 1);

        txtMessage.Dock = DockStyle.Fill;
        txtMessage.BorderStyle = BorderStyle.FixedSingle;
        txtMessage.BackColor = Color.White;
        txtMessage.ForeColor = TextMain;
        txtMessage.Font = new Font("Segoe UI", 10.5F);

        var actions = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.RightToLeft,
            WrapContents = false,
            Padding = new Padding(0, 10, 0, 0)
        };
        actions.Controls.Add(btnSend);
        actions.Controls.Add(btnCancel);

        layout.Controls.Add(header, 0, 0);
        layout.Controls.Add(CreateField("Destinataire", txtTo), 0, 1);
        layout.Controls.Add(CreateField("Sujet", txtSubject), 0, 2);
        layout.Controls.Add(txtMessage, 0, 3);
        layout.Controls.Add(actions, 0, 4);

        shell.Controls.Add(layout);
        root.Controls.Add(shell, 0, 0);
        Controls.Add(root);
    }

    private async Task SendAsync()
    {
        try
        {
            btnSend.Enabled = false;
            btnSend.Text = "Envoi...";

            if (replyTo == null)
            {
                if (string.IsNullOrWhiteSpace(txtTo.Text))
                {
                    MessageBox.Show("Destinataire obligatoire.", "Nouveau mail", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    ResetSendButton();
                    return;
                }

                var mail = new EmailMessage(service)
                {
                    Subject = txtSubject.Text,
                    Body = new MessageBody(BodyType.Text, txtMessage.Text)
                };
                mail.ToRecipients.Add(txtTo.Text.Trim());
                await Task.Run(() => mail.SendAndSaveCopy());
            }
            else
            {
                var response = replyTo.CreateReply(false);
                response.BodyPrefix = new MessageBody(BodyType.Text, txtMessage.Text);
                await Task.Run(() => response.SendAndSaveCopy());
            }

            MessageBox.Show("Mail envoye.", "Exchange", MessageBoxButtons.OK, MessageBoxIcon.Information);
            Close();
        }
        catch (Exception ex)
        {
            ResetSendButton();
            MessageBox.Show("Erreur d'envoi :\n" + ex.Message, "Exchange", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void ResetSendButton()
    {
        btnSend.Enabled = true;
        btnSend.Text = "Envoyer";
    }

    private static Control CreateField(string label, TextBox textBox)
    {
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 2,
            Padding = new Padding(0, 0, 0, 8)
        };
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        panel.Controls.Add(new Label
        {
            Text = label,
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI Semibold", 8.8F),
            ForeColor = TextMuted
        }, 0, 0);
        panel.Controls.Add(textBox, 0, 1);
        return panel;
    }

    private static TextBox CreateTextBox(string placeholder = "")
    {
        return new TextBox
        {
            Dock = DockStyle.Fill,
            PlaceholderText = placeholder,
            BorderStyle = BorderStyle.FixedSingle,
            Font = new Font("Segoe UI", 10F),
            ForeColor = TextMain
        };
    }

    private static Button CreateButton(string text, bool primary = false)
    {
        var button = new Button
        {
            Text = text,
            AutoSize = false,
            Width = primary ? 120 : 104,
            Height = 32,
            Margin = new Padding(8, 0, 0, 0),
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI Semibold", 9.5F),
            BackColor = primary ? Primary : Color.White,
            ForeColor = primary ? Color.White : TextMain,
            Cursor = Cursors.Hand
        };
        button.FlatAppearance.BorderColor = primary ? Primary : BorderColor;
        button.FlatAppearance.MouseOverBackColor = primary ? PrimaryDark : Color.FromArgb(239, 243, 248);
        button.FlatAppearance.MouseDownBackColor = primary ? PrimaryDark : Color.FromArgb(229, 235, 244);
        return button;
    }
}
