from __future__ import annotations

from pathlib import Path
from shutil import copyfile

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
SCREENSHOT_DIR = DOCS_DIR / "screenshots"
OUTPUT_PATH = DOCS_DIR / "google-ads-api-basic-access-application.pdf"
PUBLIC_OUTPUT_PATH = REPO_ROOT / "frontend" / "public" / "docs" / OUTPUT_PATH.name

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = 18 * mm
RIGHT = 18 * mm
TOP = 19 * mm
BOTTOM = 17 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT - RIGHT

NAVY = colors.HexColor("#10233D")
BLUE = colors.HexColor("#1F6FEB")
TEAL = colors.HexColor("#0F766E")
INK = colors.HexColor("#182231")
MUTED = colors.HexColor("#5F6B7A")
LINE = colors.HexColor("#D9E0E7")
PALE = colors.HexColor("#EEF3F4")
PALE_BLUE = colors.HexColor("#EDF4FF")
PALE_GREEN = colors.HexColor("#E8F5F1")
WHITE = colors.white


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/seguisb.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("AxyroRegular", str(regular)))
            pdfmetrics.registerFont(TTFont("AxyroBold", str(bold)))
            return "AxyroRegular", "AxyroBold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


class AxyroDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=LEFT,
            rightMargin=RIGHT,
            topMargin=TOP,
            bottomMargin=BOTTOM,
            title="Axyro Analytics - Google Ads API Basic Access Application",
            author="Iskhakov Ruslan",
            subject="Google Ads API Basic Access design and safety documentation",
        )
        frame = Frame(LEFT, BOTTOM, CONTENT_WIDTH, PAGE_HEIGHT - TOP - BOTTOM, id="normal")
        self.addPageTemplates(PageTemplate(id="body", frames=[frame], onPage=_draw_page_chrome))


def _draw_page_chrome(canvas, doc) -> None:
    page = canvas.getPageNumber()
    if page == 1:
        return
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT, PAGE_HEIGHT - 12 * mm, PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 12 * mm)
    canvas.setFont(FONT_BOLD, 8.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(LEFT, PAGE_HEIGHT - 9.2 * mm, "AXYRO ANALYTICS")
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 9.2 * mm, "Google Ads API Basic Access")
    canvas.line(LEFT, 11 * mm, PAGE_WIDTH - RIGHT, 11 * mm)
    canvas.drawString(LEFT, 7.5 * mm, "Confidential application documentation - no credentials or tokens")
    canvas.drawRightString(PAGE_WIDTH - RIGHT, 7.5 * mm, f"Page {page}")
    canvas.restoreState()


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverEyebrow",
        fontName=FONT_BOLD,
        fontSize=11,
        leading=14,
        textColor=TEAL,
        spaceAfter=8,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        fontName=FONT_BOLD,
        fontSize=29,
        leading=32,
        textColor=WHITE,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSubtitle",
        fontName=FONT,
        fontSize=15,
        leading=21,
        textColor=colors.HexColor("#DCE7F4"),
    )
)
styles.add(
    ParagraphStyle(
        name="H1Axyro",
        fontName=FONT_BOLD,
        fontSize=22,
        leading=26,
        textColor=NAVY,
        spaceBefore=2,
        spaceAfter=13,
    )
)
styles.add(
    ParagraphStyle(
        name="H2Axyro",
        fontName=FONT_BOLD,
        fontSize=14,
        leading=18,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=7,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyAxyro",
        fontName=FONT,
        fontSize=9.4,
        leading=14,
        textColor=INK,
        spaceAfter=7,
    )
)
styles.add(
    ParagraphStyle(
        name="BodySmall",
        fontName=FONT,
        fontSize=8.3,
        leading=12,
        textColor=MUTED,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="BulletAxyro",
        parent=styles["BodyAxyro"],
        leftIndent=14,
        firstLineIndent=-8,
        bulletIndent=0,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="CaptionAxyro",
        fontName=FONT,
        fontSize=8,
        leading=11,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceBefore=6,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="CalloutAxyro",
        fontName=FONT_BOLD,
        fontSize=10,
        leading=15,
        textColor=NAVY,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=4,
        spaceAfter=4,
    )
)


def p(text: str, style: str = "BodyAxyro") -> Paragraph:
    return Paragraph(text, styles[style])


def bullets(items: list[str]) -> list[Flowable]:
    return [Paragraph(f"• {item}", styles["BulletAxyro"]) for item in items]


def section(title: str) -> list[Flowable]:
    return [Spacer(1, 2 * mm), p(title, "H1Axyro")]


def callout(text: str, background=PALE_BLUE) -> Table:
    table = Table([[p(text, "CalloutAxyro")]], colWidths=[CONTENT_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def facts_table(rows: list[tuple[str, str]], widths: tuple[float, float] | None = None) -> Table:
    col_widths = list(widths or (52 * mm, CONTENT_WIDTH - 52 * mm))
    data = [[p(f"<b>{label}</b>", "BodySmall"), p(value, "BodySmall")] for label, value in rows]
    table = Table(data, colWidths=col_widths, repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), PALE),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


class ArchitectureDiagram(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width = CONTENT_WIDTH
        self.height = 66 * mm

    def draw(self) -> None:
        c = self.canv
        nodes = [
            ("Authorized\nuser", 3, 43, 28, 13, PALE),
            ("Caddy\nHTTPS", 39, 43, 25, 13, PALE_BLUE),
            ("React\nfrontend", 72, 43, 29, 13, PALE_BLUE),
            ("FastAPI\nbackend", 109, 43, 31, 13, PALE_GREEN),
            ("Google Ads\nAPI", 148, 43, 31, 13, colors.HexColor("#FFF4E5")),
            ("PostgreSQL\nsource of truth", 82, 14, 38, 14, PALE),
            ("Redis\ntask broker", 126, 14, 29, 14, PALE),
            ("Worker +\nscheduler", 160, 14, 31, 14, PALE),
        ]
        scale = self.width / (194 * mm)

        def x(value: float) -> float:
            return value * mm * scale

        def y(value: float) -> float:
            return value * mm

        c.saveState()
        c.setLineWidth(1)
        c.setStrokeColor(colors.HexColor("#90A2B5"))
        for start, end in [(31, 39), (64, 72), (101, 109), (140, 148)]:
            c.line(x(start), y(49.5), x(end), y(49.5))
        for x1, y1, x2, y2 in [(124, 43, 101, 28), (128, 43, 140, 28), (134, 43, 176, 28)]:
            c.line(x(x1), y(y1), x(x2), y(y2))
        for label, left, bottom, width, height, fill in nodes:
            c.setFillColor(fill)
            c.setStrokeColor(LINE)
            c.roundRect(x(left), y(bottom), x(width), y(height), 3, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.setFont(FONT_BOLD, 7.6)
            lines = label.split("\n")
            baseline = y(bottom + height / 2 + (2 if len(lines) == 2 else 0))
            for idx, line in enumerate(lines):
                c.drawCentredString(x(left + width / 2), baseline - idx * 9, line)
        c.setFont(FONT, 7.2)
        c.setFillColor(MUTED)
        c.drawString(x(7), y(3), "Credentials and Google protocol objects remain behind the backend boundary.")
        c.restoreState()


def scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    image = Image(str(path))
    ratio = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * ratio
    image.drawHeight = image.imageHeight * ratio
    return image


def screenshot_page(
    story: list[Flowable],
    number: int,
    title: str,
    description: str,
    paths: list[Path],
    caption: str,
) -> None:
    story.append(PageBreak())
    story.extend(section(f"Interface evidence {number}: {title}"))
    story.append(p(description))
    max_height = 132 * mm if len(paths) == 1 else 70 * mm
    for path in paths:
        if not path.exists():
            story.append(callout(f"Screenshot not found: {path.name}", colors.HexColor("#FFF4E5")))
            continue
        story.append(Spacer(1, 2 * mm))
        story.append(scaled_image(path, CONTENT_WIDTH, max_height))
    story.append(p(caption, "CaptionAxyro"))


def build_story() -> list[Flowable]:
    story: list[Flowable] = []

    cover_box = Table(
        [
            [p("GOOGLE ADS API BASIC ACCESS", "CoverEyebrow")],
            [p("Axyro Analytics", "CoverTitle")],
            [p("Private Google Ads Analytics &amp; Control Center", "CoverSubtitle")],
            [Spacer(1, 13 * mm)],
            [p("Design, security, workflow, and interface evidence", "CoverSubtitle")],
        ],
        colWidths=[CONTENT_WIDTH],
        rowHeights=[None, None, None, 13 * mm, None],
    )
    cover_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 14 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14 * mm),
                ("TOPPADDING", (0, 0), (-1, 0), 17 * mm),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 17 * mm),
            ]
        )
    )
    story.append(Spacer(1, 12 * mm))
    story.append(cover_box)
    story.append(Spacer(1, 14 * mm))
    story.append(
        facts_table(
            [
                ("Operator", "Iskhakov Ruslan"),
                ("Legal status", "Individual; no registered company"),
                ("Product status", "Independent software project; not a separate legal entity"),
                ("Website", '<link href="https://axyro.tech" color="#1F6FEB">https://axyro.tech</link>'),
                ("Developer-token MCC", "558-933-5362"),
                ("Google Cloud Project Number", "1044664056304"),
                ("Contact", "support@axyro.tech"),
                ("Document date", "August 18, 2026"),
            ]
        )
    )
    story.append(Spacer(1, 7 * mm))
    story.append(
        callout(
            "This document contains no Developer Token, OAuth Client Secret, refresh token, access token, password, encryption key, or private key.",
            PALE_GREEN,
        )
    )

    story.append(PageBreak())
    story.extend(section("1. Executive summary"))
    for text in [
        "Axyro Analytics is an independent Google Ads analytics and operations software project operated by Iskhakov Ruslan, an individual. Axyro Analytics is the project name, not a registered company or separate legal entity. The private tool consolidates connected manager and advertising accounts into a single control center.",
        "The platform synchronizes account hierarchy, campaign performance metrics, conversion data, policy and verification statuses, operational issues, and change history. Its sole user can analyze accounts across different geographic markets, apply filters and saved views, compare performance, review alerts, maintain notes, and export reports.",
        "The primary purpose of the tool is centralized reporting, performance analysis, account monitoring, and operational control.",
        "The platform also includes secondary campaign management functions. Authorized users can create validated Demand Gen campaigns, pause or enable selected campaigns, and update budgets. All write operations are explicitly initiated by a user, validated before execution, confirmed in the interface, recorded in an audit log, and protected by production safety controls. Newly created campaigns are created in a paused state by default.",
        "Only Iskhakov Ruslan currently has access. There are no employees, contractors, external clients, or public users, and the platform is not offered as a public self-service advertising product.",
    ]:
        story.append(p(text))
    story.append(Spacer(1, 3 * mm))
    story.append(callout("Primary use: reporting, analytics and monitoring. Secondary use: explicitly confirmed campaign management operations."))

    story.extend(section("2. Why Basic Access is required"))
    story.append(
        p(
            "Basic Access is required to analyze and manage production Google Ads accounts that Iskhakov Ruslan is authorized to access through his manager account. Test accounts do not serve ads and therefore cannot provide the real performance metrics, conversion data, policy statuses, verification states, account activity, and operational history required to validate the analytics and monitoring functions of the platform."
        )
    )
    story.append(p("The requested access will be used only for accounts that Iskhakov Ruslan is authorized to manage and that are linked to his Google Ads manager account."))

    story.extend(section("3. Ownership, business model, and audience"))
    story.append(
        p(
            "The applicant and operator is <b>Iskhakov Ruslan</b>, an individual developer and advertiser who does not represent a registered company. Axyro Analytics is a project name used for his privately operated software; it is not a separate legal entity, advertising agency, public SaaS product, or API resale service."
        )
    )
    story.append(p("The current deployment is used only by Iskhakov Ruslan through the owner ADMIN account. No employee, contractor, external client, or other person has access. The role types below are technical authorization boundaries and do not imply that a team currently uses the application."))
    story.append(Spacer(1, 2 * mm))
    story.extend(
        bullets(
            [
                "ADMIN - protected connections, permitted confirmations, settings, and audit review.",
                "OPERATOR - analytics, planning, and permitted operational workflows.",
                "VIEWER - read-only reporting and monitoring.",
            ]
        )
    )

    story.append(PageBreak())
    story.extend(section("4. Architecture and credential boundary"))
    story.append(p("The production deployment uses seven isolated Docker services. PostgreSQL is the source of truth; Redis transports bounded background work. Google Ads protocol objects and credentials remain inside the backend adapter."))
    story.append(Spacer(1, 4 * mm))
    story.append(ArchitectureDiagram())
    story.append(Spacer(1, 4 * mm))
    story.extend(
        bullets(
            [
                "Caddy terminates HTTPS and proxies only the public frontend and /api routes.",
                "React frontend never receives the Developer Token, OAuth Client Secret, access token, refresh token, or encryption key.",
                "FastAPI enforces server-side sessions, CSRF, role authorization, trusted hosts, CORS, and audit recording.",
                "Celery worker and scheduler execute bounded, persisted jobs; queued does not mean successful.",
                "A versioned Google Ads adapter isolates GAQL, validate_only, mutate, readback, error codes, and Request IDs.",
            ]
        )
    )

    story.extend(section("5. OAuth and MCC discovery"))
    story.append(p("OAuth uses the Google Ads scope, exact HTTPS callback, state, PKCE, short-lived authorization records, and encrypted refresh-token storage."))
    story.append(callout("Public callback: https://axyro.tech/api/google-connections/oauth/callback", PALE_GREEN))
    story.append(
        facts_table(
            [
                ("Production developer-token MCC", "558-933-5362"),
                ("Isolated Google Test MCC", "383-107-3849"),
                ("Verified test clients", "183-386-9760 and 804-728-0949"),
                ("Discovery", "ListAccessibleCustomers + recursive customer_client GAQL + customer GAQL"),
            ]
        )
    )

    story.append(PageBreak())
    story.extend(section("6. Google Ads API operations"))
    operation_rows = [
        [p("Primary read operations", "H2Axyro"), p("Secondary write operations", "H2Axyro")],
        [
            p("Accessible customers and MCC hierarchy<br/>Account and campaign configuration<br/>Cost, impressions, clicks, CTR, CPC<br/>Mapped registrations, deposits, and CPA<br/>Policy and verification status<br/>Change history and supported billing data<br/>Post-operation GAQL readback", "BodySmall"),
            p("Validated Demand Gen creation<br/>Pause selected campaigns<br/>Enable selected campaigns<br/>Update selected campaign budgets<br/><br/><b>Every write is user initiated, previewed, validated, explicitly confirmed, audited, and read back.</b>", "BodySmall"),
        ],
    ]
    operations = Table(operation_rows, colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2])
    operations.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                ("BACKGROUND", (1, 0), (1, -1), PALE_GREEN),
                ("GRID", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(operations)
    story.append(Spacer(1, 5 * mm))
    story.append(callout("Current production state: API Center shows Test Account Access. Production mutation is hard-blocked and production mutation count is zero.", colors.HexColor("#FFF4E5")))

    story.extend(section("7. Validated campaign deployment"))
    story.extend(
        bullets(
            [
                "Select an authorized connection, MCC, and child accounts.",
                "Build an immutable preliminary campaign plan.",
                "Validate schema, budgets, targeting, assets, URLs, and domain availability or reputation.",
                "Refresh account and hierarchy state and call Google Ads validate_only.",
                "Present the complete plan and financial preview.",
                "Require explicit confirmation from the same authenticated user.",
                "Create each new campaign in PAUSED; never enable it automatically.",
                "Read every resource back and store results and Request IDs in AuditLog.",
            ]
        )
    )

    story.extend(section("8. Manual campaign control"))
    story.append(p("PAUSE, ENABLE, and budget updates use fresh read, preview, confirmation, stale-state rejection, validate_only, mutate, Request ID persistence, GAQL readback, comparison, and audit. Success is reported only after matching readback."))

    story.append(PageBreak())
    story.extend(section("9. Production safety controls"))
    story.extend(
        bullets(
            [
                "Current hard production-mutation block while Basic Access is pending.",
                "Server-side role authorization and exact connection/target hierarchy checks.",
                "Exact login_customer_id and fresh confirmation that the target is a client, not an MCC.",
                "Immutable preview fingerprint and stale-state rejection.",
                "Local validation, Google validate_only, and explicit confirmation.",
                "Idempotency keys, duplicate protection, bounded retries, and circuit breaker.",
                "Campaign-level failure isolation; unrelated package items may continue safely.",
                "15,000-operation internal daily planning limit with a 20% manual reserve.",
                "AuditLog, Google Request IDs, and post-mutation readback.",
                "Automatic rules remain DRY RUN by default.",
            ]
        )
    )

    story.extend(section("10. Security, audit, retention, and deletion"))
    story.append(
        facts_table(
            [
                ("Transport", "HTTPS, HSTS, reverse-proxy security headers"),
                ("Authentication", "Server-side sessions, secure cookies, CSRF, roles"),
                ("OAuth protection", "Exact callback, state, PKCE, encrypted refresh tokens"),
                ("Secrets", "Backend only; redacted from responses, logs, exports, and screenshots"),
                ("Audit", "Actor, action, old/requested/actual values, mode, resources, Request IDs"),
                ("Errors", "Google code, category, safe message, Request ID; never masked as success"),
                ("Disconnect", "Stored refresh token for the connection is cleared immediately"),
                ("Backups", "Encrypted production backup rotation: 14 days"),
                ("Deletion contact", "support@axyro.tech"),
            ]
        )
    )

    story.extend(section("11. Public documentation"))
    story.extend(
        bullets(
            [
                '<link href="https://axyro.tech" color="#1F6FEB">Product page - https://axyro.tech/</link>',
                '<link href="https://axyro.tech/privacy" color="#1F6FEB">Privacy Policy - https://axyro.tech/privacy</link>',
                '<link href="https://axyro.tech/terms" color="#1F6FEB">Terms of Use - https://axyro.tech/terms</link>',
                '<link href="https://axyro.tech/docs/google-ads-api-basic-access-application.pdf" color="#1F6FEB">This PDF - public copy</link>',
            ]
        )
    )
    story.append(p("Axyro Analytics is an independent software project operated by Iskhakov Ruslan, an individual. It is not a registered company or separate legal entity and is not affiliated with, endorsed by, or sponsored by Google."))

    screenshot_page(
        story,
        1,
        "overall analytics dashboard",
        "The Control Center is the primary product surface. It combines account totals, spend, campaign activity, attention states, operation planning, and a portfolio table.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "Acceptance-fixture data is used for this screenshot; it is clearly separated from real Google Test and production data.",
    )
    screenshot_page(
        story,
        2,
        "accounts in work",
        "Local working statuses are independent from Google status. The In work filter keeps operational ownership visible even when Google status requires attention.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "Accounts can be moved between Unclassified, Preparation, In work, Paused, and Archive without changing Google Ads state.",
    )
    screenshot_page(
        story,
        3,
        "GEO and MCC grouping",
        "The account table supports MCC, GEO, currency, tag, Google-status, and saved-view context. Hierarchy and local grouping remain separate from raw Customer IDs.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "MCC hierarchy comes from Google; GEO and local names are internal organizational metadata.",
    )
    screenshot_page(
        story,
        4,
        "spend and conversion metrics",
        "Portfolio rows and summaries expose spend and mapped conversions. Registration and deposit mappings are explicit, and missing data is never converted into a false zero.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "Supported metrics include cost, impressions, clicks, CTR, CPC, registrations, deposits, and CPA.",
    )
    screenshot_page(
        story,
        5,
        "issues and statuses",
        "Separate views expose synchronization failures, account status, campaign status, policy issues, advertiser verification, and operational alerts.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "A severe confirmed policy or access problem remains visible regardless of local work status.",
    )
    screenshot_page(
        story,
        6,
        "filters and saved views",
        "Search, period, account-time-zone mode, MCC, Google status, currency, tags, configurable columns, and saved views support repeatable reporting.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "CSV and XLSX exports use the current authorized view and never include protected credentials.",
    )
    screenshot_page(
        story,
        7,
        "history and AuditLog",
        "Operational history records PAUSE and ENABLE results while the independent AuditLog keeps actor, target, request, result, and timestamp evidence.",
        [SCREENSHOT_DIR / "manual-actions-history-desktop.png"],
        "The displayed fixture is SIMULATION and is labelled accordingly; real Google actions additionally persist Request IDs and readback.",
    )
    screenshot_page(
        story,
        8,
        "account notes and tags",
        "Account rows support editable internal notes, local names, tags, work status, and history. These fields never alter the corresponding Google Ads account.",
        [SCREENSHOT_DIR / "control-center-desktop.png"],
        "Internal context is stored in PostgreSQL and protected by application roles and AuditLog.",
    )
    screenshot_page(
        story,
        9,
        "campaigns and statistics",
        "The campaign view combines source, type, status, budget, and available statistics. This screenshot shows the isolated real Google Test fixtures.",
        [SCREENSHOT_DIR / "google-test-control-center-desktop.png"],
        "Google Test accounts do not serve ads; missing delivery metrics are displayed as no data rather than synthetic values.",
    )
    screenshot_page(
        story,
        10,
        "validated Demand Gen deployment",
        "Only after analytics and operational-control evidence, the secondary wizard demonstrates financial preview, local validation, Google validate_only, confirmation, and creation in PAUSED.",
        [SCREENSHOT_DIR / "financial-preview-desktop.png", SCREENSHOT_DIR / "creation-paused-desktop.png"],
        "The acceptance fixture is SIMULATION. Separate real Google Test evidence confirmed validate_only, creation, Request IDs, and PAUSED readback; production mutation remains zero.",
    )

    story.append(PageBreak())
    story.extend(section("12. Application readiness checklist"))
    checklist_rows = [
        ("Public identity", "Iskhakov Ruslan - individual operator; Axyro Analytics is a project, not a company or legal entity"),
        ("Website", "Publicly accessible without authentication"),
        ("Privacy and Terms", "Public English/Russian pages with Google Ads API use and deletion contact"),
        ("API Center", "Developer-token MCC 558-933-5362; Test Account Access; Basic Access application available"),
        ("Google Cloud", "Project Number 1044664056304; OAuth callback uses https://axyro.tech"),
        ("Write disclosure", "Demand Gen creation, PAUSE, ENABLE, and budget update are explicitly documented"),
        ("Production state", "Mutations blocked; zero production mutations"),
        ("Form", "Answers prepared for sole individual use; confirmation checkboxes and Submit intentionally untouched"),
    ]
    story.append(facts_table(checklist_rows, (49 * mm, CONTENT_WIDTH - 49 * mm)))
    story.append(Spacer(1, 7 * mm))
    story.append(callout("Prepared for owner review. This document does not authorize submission of the Basic Access application.", PALE_GREEN))

    return story


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = AxyroDocTemplate(str(OUTPUT_PATH))
    document.build(build_story())
    PUBLIC_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    copyfile(OUTPUT_PATH, PUBLIC_OUTPUT_PATH)
    print(f"Created {OUTPUT_PATH}")
    print(f"Published source copy {PUBLIC_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
