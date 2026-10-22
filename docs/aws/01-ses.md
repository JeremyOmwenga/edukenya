# AWS setup 01: Amazon SES (sending email)

What this gives us: EduKenya can send verification emails from `no-reply@<your-domain>`, signed with DKIM so they land in inboxes, not spam.

Region: use **eu-west-1 (Ireland)** for every EduKenya resource. It has good latency to Nairobi and the widest choice of Bedrock AI models, which we need later for the RAG side. Mixing regions causes confusing "resource not found" errors, so always check the region picker (top right of the console) first.

Time needed: about 20 minutes of clicking, then waiting for DNS (usually minutes, can take up to a few hours) and for AWS to approve production access (usually within 24 hours).

## Step 1: Deploy the CloudFormation stack

1. Sign in to the AWS console. Top right, set the region to **Europe (Ireland) eu-west-1**.
2. Search for **CloudFormation** in the top search bar and open it.
3. Click **Create stack** > **With new resources (standard)**.
4. Choose **Upload a template file**, pick `infra/cloudformation/ses.yaml` from this repo, click **Next**.
5. Stack name: `edukenya-ses`. DomainName: your Cloudflare domain, lowercase, e.g. `edukenya.co.ke`. Leave MailFromSubdomain as `mail`. Click **Next**.
6. On the options page change nothing, click **Next**.
7. On the review page, scroll down and tick **"I acknowledge that AWS CloudFormation might create IAM resources with custom names"**, then **Submit**.
8. Wait until the status says **CREATE_COMPLETE** (1 to 2 minutes, use the refresh button).

## Step 2: Add the DNS records in Cloudflare

Open the **Outputs** tab of the `edukenya-ses` stack. Keep it open next to Cloudflare.

In Cloudflare: select your domain > **DNS** > **Records** > **Add record** for each row below.

| Type | Name | Content / Target | Notes |
|---|---|---|---|
| CNAME | value of `Dkim1Name` | value of `Dkim1Value` | Proxy status **DNS only** (grey cloud) |
| CNAME | value of `Dkim2Name` | value of `Dkim2Value` | **DNS only** |
| CNAME | value of `Dkim3Name` | value of `Dkim3Value` | **DNS only** |
| MX | `mail` | `feedback-smtp.eu-west-1.amazonses.com` | Priority `10` |
| TXT | `mail` | `v=spf1 include:amazonses.com ~all` | |
| TXT | `_dmarc` | `v=DMARC1; p=none;` | Skip if a `_dmarc` record already exists |

Two things trip people up:
- The DKIM CNAMEs **must be grey cloud (DNS only)**. Orange cloud (proxied) breaks verification.
- You can paste the full name from the Outputs (it ends in your domain). Cloudflare accepts it and shortens it automatically.

## Step 3: Confirm SES verified the domain

1. Open **Amazon SES** in the console (still eu-west-1) > **Identities** > click your domain.
2. Wait until you see: Identity status **Verified**, DKIM **Successful**, Custom MAIL FROM **Successful**.
   Refresh every few minutes. If it is still pending after a few hours, recheck the grey cloud and spelling of the records.

## Step 4: Verify your own email (needed while in the sandbox)

New SES accounts start in a **sandbox**: you can only send to addresses you have verified.

1. SES > **Identities** > **Create identity** > **Email address**.
2. Enter your personal email, click **Create identity**, then click the link AWS emails you.

## Step 5: Request production access

This lets EduKenya email any school admin, not just you.

1. SES > **Account dashboard** > **Request production access**.
2. Mail type: **Transactional**. Website URL: your domain.
3. Use case description, something like:
   > EduKenya is a learning platform for Kenyan CBC schools. We send transactional email only: account verification links, password resets and school approval notices to users who sign up on our site. We do not send marketing email. Addresses that bounce or complain are suppressed automatically through our SES configuration set.
4. Submit. AWS usually replies within 24 hours. Meanwhile, everything works for your verified address.

## Step 6: Create the access key for local development

1. Open **IAM** > **Users** > `edukenya-ses-sender` > **Security credentials** tab.
2. **Create access key** > choose **Application running outside AWS** > **Next** > **Create access key**.
3. Copy both values into your local `.env` (copy `.env.example` to `.env` first):
   ```
   AWS_SES_ACCESS_KEY_ID=<access key id>
   AWS_SES_SECRET_ACCESS_KEY=<secret access key>
   DEFAULT_FROM_EMAIL=EduKenya <no-reply@your-domain>
   ```
   The secret is only shown once. Never paste it in chat, commit it, or share screenshots of it. This user can only send email from your domain, nothing else.

When we deploy to AWS, the app gets an IAM role instead and this key is not used there.

## Step 7: Send a test email

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py sendtestemail you@your-verified-address.com
```

It should arrive within a minute. In Gmail, open it > **Show original** and check that SPF, DKIM and DMARC all say **PASS**.

Common errors:
- `MessageRejected: Email address is not verified`: still in the sandbox and the recipient is not verified (Step 4), or `DEFAULT_FROM_EMAIL` does not use your verified domain.
- `InvalidClientTokenId` / `SignatureDoesNotMatch`: access key copied wrong in `.env`.
- `AccessDenied`: the From address is not `@your-domain`.
