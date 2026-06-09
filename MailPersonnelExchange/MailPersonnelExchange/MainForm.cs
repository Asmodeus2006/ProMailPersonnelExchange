using Microsoft.Exchange.WebServices.Data;
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Net;
using Task = System.Threading.Tasks.Task;
using System.Windows.Forms;

namespace MailPersonnelExchange;

public class MainForm : Form
{
    private static readonly Color AppBack = Color.FromArgb(245, 247, 250);
    private static readonly Color PanelBack = Color.White;
    private static readonly Color BorderColor = Color.FromArgb(219, 226, 236);
    private static readonly Color Primary = Color.FromArgb(20, 93, 160);
    private static readonly Color PrimaryDark = Color.FromArgb(13, 69, 121);
    private static readonly Color TextMain = Color.FromArgb(31, 41, 55);
    private static readonly Color TextMuted = Color.FromArgb(91, 105, 123);
    private static readonly Color Success = Color.FromArgb(30, 132, 73);

    private readonly TextBox txtEmail = CreateTextBox("prenom.nom@promed-lab.ch");
    private readonly TextBox txtDomain = CreateTextBox();
    private readonly TextBox txtNip = CreateTextBox("NIP / utilisateur AD");
    private readonly TextBox txtPassword = CreateTextBox("Mot de passe");
    private readonly TextBox txtEwsUrl = CreateTextBox();
    private readonly TextBox txtSearch = CreateTextBox("Rechercher dans les mails charges");

    private readonly Button btnConnect = CreateButton("Connexion", true);
    private readonly Button btnLogout = CreateButton("Deconnexion");
    private readonly Button btnRefresh = CreateButton("Actualiser");
    private readonly Button btnReply = CreateButton("Repondre");
    private readonly Button btnNew = CreateButton("Nouveau mail", true);
    private readonly Button btnClearSearch = CreateButton("Effacer");

    private readonly Label lblStatus = new();
    private readonly Label lblMailboxTitle = new();
    private readonly Label lblPreviewTitle = new();
    private readonly Label lblPreviewMeta = new();
    private readonly ListView lstMails = new();
    private readonly RichTextBox txtBody = new();
    private readonly StatusStrip statusStrip = new();
    private readonly ToolStripStatusLabel toolStatus = new();

    private ExchangeService? service;
    private readonly List<EmailMessage> currentMessages = new();
    private readonly List<EmailMessage> visibleMessages = new();

    public MainForm()
    {
        Text = "Mail personnel Exchange";
        MinimumSize = new Size(1180, 760);
        Size = new Size(1280, 820);
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 10F);
        BackColor = AppBack;

        txtDomain.Text = "GAMBA-SMCF";
        txtPassword.UseSystemPasswordChar = true;
        txtEwsUrl.Text = "https://email.promed-lab.ch/EWS/Exchange.asmx";

        BuildLayout();
        WireEvents();
        SetConnected(false);
        ShowEmptyPreview();
    }

    private void BuildLayout()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = AppBack,
            ColumnCount = 1,
            RowCount = 3,
            Padding = new Padding(18)
        };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 178));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));

        root.Controls.Add(BuildTopPanel(), 0, 0);
        root.Controls.Add(BuildMailPanel(), 0, 1);

        statusStrip.BackColor = AppBack;
        statusStrip.SizingGrip = false;
        toolStatus.ForeColor = TextMuted;
        toolStatus.Text = "Pret";
        statusStrip.Items.Add(toolStatus);
        root.Controls.Add(statusStrip, 0, 2);

        Controls.Add(root);
    }

    private Control BuildTopPanel()
    {
        var shell = CreatePanel();
        shell.Padding = new Padding(18, 16, 18, 14);

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 3
        };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));

        var header = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2 };
        header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        header.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 260));

        var title = new Label
        {
            Text = "Messagerie Exchange",
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI Semibold", 15F),
            ForeColor = TextMain,
            TextAlign = ContentAlignment.MiddleLeft
        };
        lblStatus.Dock = DockStyle.Fill;
        lblStatus.Font = new Font("Segoe UI Semibold", 10F);
        lblStatus.ForeColor = TextMuted;
        lblStatus.TextAlign = ContentAlignment.MiddleRight;

        header.Controls.Add(title, 0, 0);
        header.Controls.Add(lblStatus, 1, 0);

        var fields = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 5, Padding = new Padding(0, 8, 0, 0) };
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 13));
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 16));
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 18));
        fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 28));
        fields.Controls.Add(CreateField("Adresse mail", txtEmail), 0, 0);
        fields.Controls.Add(CreateField("Domaine", txtDomain), 1, 0);
        fields.Controls.Add(CreateField("NIP", txtNip), 2, 0);
        fields.Controls.Add(CreateField("Mot de passe", txtPassword), 3, 0);
        fields.Controls.Add(CreateField("URL EWS", txtEwsUrl), 4, 0);

        var actions = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 4, 0, 0)
        };
        actions.Controls.Add(btnConnect);
        actions.Controls.Add(btnNew);
        actions.Controls.Add(btnReply);
        actions.Controls.Add(btnRefresh);
        actions.Controls.Add(btnLogout);

        layout.Controls.Add(header, 0, 0);
        layout.Controls.Add(fields, 0, 1);
        layout.Controls.Add(actions, 0, 2);
        shell.Controls.Add(layout);
        return shell;
    }

    private Control BuildMailPanel()
    {
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = AppBack
        };
        bool splitConfigured = false;
        split.SizeChanged += (_, _) =>
        {
            if (splitConfigured || split.Width < 900) return;

            split.Panel1MinSize = 320;
            split.Panel2MinSize = 420;
            split.SplitterDistance = Math.Min(470, split.Width - split.Panel2MinSize);
            splitConfigured = true;
        };

        split.Panel1.Padding = new Padding(0, 14, 8, 0);
        split.Panel2.Padding = new Padding(8, 14, 0, 0);
        split.Panel1.Controls.Add(BuildMailboxPanel());
        split.Panel2.Controls.Add(BuildPreviewPanel());
        return split;
    }

    private Control BuildMailboxPanel()
    {
        var shell = CreatePanel();
        shell.Padding = new Padding(14);

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        lblMailboxTitle.Text = "Boite de reception";
        lblMailboxTitle.Dock = DockStyle.Fill;
        lblMailboxTitle.Font = new Font("Segoe UI Semibold", 12F);
        lblMailboxTitle.ForeColor = TextMain;

        var searchPanel = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2 };
        searchPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        searchPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 92));
        searchPanel.Controls.Add(txtSearch, 0, 0);
        searchPanel.Controls.Add(btnClearSearch, 1, 0);

        lstMails.Dock = DockStyle.Fill;
        lstMails.View = View.Details;
        lstMails.FullRowSelect = true;
        lstMails.HideSelection = false;
        lstMails.MultiSelect = false;
        lstMails.BorderStyle = BorderStyle.FixedSingle;
        lstMails.BackColor = Color.White;
        lstMails.ForeColor = TextMain;
        lstMails.HeaderStyle = ColumnHeaderStyle.Nonclickable;
        lstMails.Columns.Add("Date", 112);
        lstMails.Columns.Add("Expediteur", 170);
        lstMails.Columns.Add("Sujet", 360);

        layout.Controls.Add(lblMailboxTitle, 0, 0);
        layout.Controls.Add(searchPanel, 0, 1);
        layout.Controls.Add(lstMails, 0, 2);
        shell.Controls.Add(layout);
        return shell;
    }

    private Control BuildPreviewPanel()
    {
        var shell = CreatePanel();
        shell.Padding = new Padding(18);

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        lblPreviewTitle.Dock = DockStyle.Fill;
        lblPreviewTitle.Font = new Font("Segoe UI Semibold", 15F);
        lblPreviewTitle.ForeColor = TextMain;
        lblPreviewTitle.AutoEllipsis = true;

        lblPreviewMeta.Dock = DockStyle.Fill;
        lblPreviewMeta.Font = new Font("Segoe UI", 9.5F);
        lblPreviewMeta.ForeColor = TextMuted;
        lblPreviewMeta.AutoEllipsis = true;

        txtBody.Dock = DockStyle.Fill;
        txtBody.BorderStyle = BorderStyle.None;
        txtBody.BackColor = PanelBack;
        txtBody.ForeColor = TextMain;
        txtBody.Font = new Font("Segoe UI", 10.5F);
        txtBody.ReadOnly = true;
        txtBody.DetectUrls = true;

        layout.Controls.Add(lblPreviewTitle, 0, 0);
        layout.Controls.Add(lblPreviewMeta, 0, 1);
        layout.Controls.Add(txtBody, 0, 2);
        shell.Controls.Add(layout);
        return shell;
    }

    private void WireEvents()
    {
        btnConnect.Click += async (_, _) => await ConnectAsync();
        btnRefresh.Click += async (_, _) => await LoadInboxAsync();
        btnLogout.Click += (_, _) => Logout();
        btnReply.Click += (_, _) => ReplyToSelected();
        btnNew.Click += (_, _) => OpenCompose(null);
        btnClearSearch.Click += (_, _) => txtSearch.Clear();
        txtSearch.TextChanged += (_, _) => ApplyFilter();
        lstMails.SelectedIndexChanged += async (_, _) => await DisplaySelectedMailAsync();
        lstMails.DoubleClick += (_, _) => ReplyToSelected();
    }

    private void SetConnected(bool connected)
    {
        btnRefresh.Enabled = connected;
        btnReply.Enabled = connected && lstMails.SelectedItems.Count > 0;
        btnNew.Enabled = connected;
        btnLogout.Enabled = connected;
        btnConnect.Enabled = !connected;
        lblStatus.Text = connected ? "Connecte a Exchange" : "Non connecte";
        lblStatus.ForeColor = connected ? Success : TextMuted;
        toolStatus.Text = connected ? "Session active" : "Renseigne tes identifiants puis clique sur Connexion.";
    }

    private async Task ConnectAsync()
    {
        if (string.IsNullOrWhiteSpace(txtEmail.Text) || string.IsNullOrWhiteSpace(txtNip.Text) || string.IsNullOrWhiteSpace(txtPassword.Text))
        {
            MessageBox.Show("Adresse mail, NIP et mot de passe sont obligatoires.", "Connexion", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        try
        {
            SetBusy("Connexion en cours...");
            btnConnect.Enabled = false;

            service = new ExchangeService(ExchangeVersion.Exchange2013_SP1)
            {
                Credentials = new NetworkCredential(txtNip.Text.Trim(), txtPassword.Text, txtDomain.Text.Trim()),
                Url = new Uri(txtEwsUrl.Text.Trim())
            };

            await Task.Run(() => service.FindFolders(WellKnownFolderName.MsgFolderRoot, new FolderView(1)));
            SetConnected(true);
            await LoadInboxAsync();
        }
        catch (Exception ex)
        {
            service = null;
            SetConnected(false);
            MessageBox.Show("Connexion impossible :\n" + ex.Message, "Erreur Exchange", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task LoadInboxAsync()
    {
        if (service == null) return;

        try
        {
            SetBusy("Chargement de la boite de reception...");
            lstMails.Items.Clear();
            txtBody.Clear();
            currentMessages.Clear();
            visibleMessages.Clear();
            ShowEmptyPreview();

            var view = new ItemView(75)
            {
                OrderBy = { { ItemSchema.DateTimeReceived, SortDirection.Descending } },
                PropertySet = new PropertySet(BasePropertySet.IdOnly, ItemSchema.Subject, ItemSchema.DateTimeReceived, EmailMessageSchema.From)
            };

            FindItemsResults<Item> results = await Task.Run(() => service.FindItems(WellKnownFolderName.Inbox, view));

            foreach (var item in results.Items)
            {
                if (item is EmailMessage msg)
                {
                    currentMessages.Add(msg);
                }
            }

            ApplyFilter();
            lblMailboxTitle.Text = $"Boite de reception - {currentMessages.Count} mail(s)";
            lblStatus.Text = "Connecte a Exchange";
            lblStatus.ForeColor = Success;
            toolStatus.Text = $"{currentMessages.Count} mail(s) charges.";
        }
        catch (Exception ex)
        {
            toolStatus.Text = "Erreur de chargement.";
            MessageBox.Show("Erreur de chargement :\n" + ex.Message, "Boite de reception", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task DisplaySelectedMailAsync()
    {
        btnReply.Enabled = service != null && lstMails.SelectedItems.Count > 0;
        if (service == null || lstMails.SelectedItems.Count == 0) return;

        try
        {
            int index = lstMails.SelectedItems[0].Index;
            if (index < 0 || index >= visibleMessages.Count) return;

            SetBusy("Ouverture du mail...");
            var selected = visibleMessages[index];
            var msg = await Task.Run(() => EmailMessage.Bind(service, selected.Id, new PropertySet(
                BasePropertySet.FirstClassProperties,
                EmailMessageSchema.TextBody,
                EmailMessageSchema.From,
                EmailMessageSchema.ToRecipients,
                ItemSchema.Subject,
                ItemSchema.DateTimeReceived)));

            lblPreviewTitle.Text = string.IsNullOrWhiteSpace(msg.Subject) ? "(Sans sujet)" : msg.Subject;
            lblPreviewMeta.Text = $"De : {FormatMailbox(msg.From)}    A : {string.Join("; ", msg.ToRecipients.Select(FormatMailbox))}    Date : {msg.DateTimeReceived:dd.MM.yyyy HH:mm}";
            txtBody.Text = msg.TextBody?.Text ?? "[Aucun contenu texte]";
            toolStatus.Text = "Mail affiche.";
        }
        catch (Exception ex)
        {
            toolStatus.Text = "Impossible d'afficher le mail.";
            MessageBox.Show("Impossible d'afficher le mail :\n" + ex.Message, "Lecture du mail", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void ReplyToSelected()
    {
        if (lstMails.SelectedItems.Count == 0)
        {
            MessageBox.Show("Selectionne d'abord un mail.", "Repondre", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        int index = lstMails.SelectedItems[0].Index;
        if (index >= 0 && index < visibleMessages.Count)
        {
            OpenCompose(visibleMessages[index]);
        }
    }

    private void OpenCompose(EmailMessage? replyTo)
    {
        if (service == null) return;
        using var compose = new ComposeForm(service, replyTo);
        compose.ShowDialog(this);
    }

    private void Logout()
    {
        service = null;
        txtPassword.Clear();
        lstMails.Items.Clear();
        txtBody.Clear();
        currentMessages.Clear();
        visibleMessages.Clear();
        lblMailboxTitle.Text = "Boite de reception";
        ShowEmptyPreview();
        SetConnected(false);
        GC.Collect();
    }

    private void ApplyFilter()
    {
        string query = txtSearch.Text.Trim();
        IEnumerable<EmailMessage> messages = currentMessages;

        if (!string.IsNullOrWhiteSpace(query))
        {
            messages = messages.Where(m =>
                (m.Subject ?? string.Empty).Contains(query, StringComparison.OrdinalIgnoreCase) ||
                FormatMailbox(m.From).Contains(query, StringComparison.OrdinalIgnoreCase));
        }

        visibleMessages.Clear();
        visibleMessages.AddRange(messages);

        lstMails.BeginUpdate();
        lstMails.Items.Clear();
        foreach (var msg in visibleMessages)
        {
            string from = FormatMailbox(msg.From);
            string subject = string.IsNullOrWhiteSpace(msg.Subject) ? "(Sans sujet)" : msg.Subject;
            var row = new ListViewItem(msg.DateTimeReceived.ToString("dd.MM.yyyy HH:mm"));
            row.SubItems.Add(from);
            row.SubItems.Add(subject);
            lstMails.Items.Add(row);
        }
        lstMails.EndUpdate();

        btnReply.Enabled = service != null && lstMails.SelectedItems.Count > 0;
        toolStatus.Text = string.IsNullOrWhiteSpace(query)
            ? $"{visibleMessages.Count} mail(s) affiches."
            : $"{visibleMessages.Count} resultat(s) pour \"{query}\".";
    }

    private void ShowEmptyPreview()
    {
        lblPreviewTitle.Text = "Aucun mail selectionne";
        lblPreviewMeta.Text = "Selectionne un message dans la boite de reception pour afficher son contenu.";
        txtBody.Text = string.Empty;
    }

    private void SetBusy(string message)
    {
        lblStatus.Text = message;
        lblStatus.ForeColor = PrimaryDark;
        toolStatus.Text = message;
    }

    private static string FormatMailbox(EmailAddress? address)
    {
        if (address == null) return "Expediteur inconnu";
        if (!string.IsNullOrWhiteSpace(address.Name) && !string.IsNullOrWhiteSpace(address.Address))
        {
            return $"{address.Name} <{address.Address}>";
        }

        return address.Name ?? address.Address ?? "Expediteur inconnu";
    }

    private static Panel CreatePanel()
    {
        return new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = PanelBack,
            BorderStyle = BorderStyle.FixedSingle
        };
    }

    private static Control CreateField(string label, TextBox textBox)
    {
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 2,
            Padding = new Padding(0, 0, 10, 0)
        };
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        panel.Controls.Add(new Label
        {
            Text = label,
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI Semibold", 8.8F),
            ForeColor = TextMuted,
            TextAlign = ContentAlignment.MiddleLeft
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
            ForeColor = TextMain,
            Margin = new Padding(0, 0, 8, 0)
        };
    }

    private static Button CreateButton(string text, bool primary = false)
    {
        var button = new Button
        {
            Text = text,
            AutoSize = false,
            Width = primary ? 136 : 116,
            Height = 32,
            Margin = new Padding(0, 0, 8, 0),
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
