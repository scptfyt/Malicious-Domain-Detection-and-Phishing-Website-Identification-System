from __future__ import annotations


def build_bootstrap_samples():
    benign_roots = [
        "baidu",
        "aliyun",
        "qq",
        "wechat",
        "github",
        "microsoft",
        "google",
        "apple",
        "amazon",
        "jd",
        "taobao",
        "alipay",
        "openai",
        "cloudflare",
        "oracle",
    ]
    benign_suffixes = ["com", "cn", "net", "org"]
    benign_paths = ["", "/login", "/help", "/home", "/portal", "/docs"]

    malicious_bases = [
        "secure-login",
        "account-verify",
        "update-password",
        "paypal-check",
        "bank-confirm",
        "signin-auth",
        "cloud-verify",
        "security-alert",
        "invoice-pay",
        "mail-login",
    ]
    malicious_tlds = ["top", "xyz", "icu", "click", "live", "pw"]
    malicious_paths = ["", "/login", "/verify", "/account", "/update", "/auth"]

    samples = []
    for idx, root in enumerate(benign_roots, 1):
        for suffix in benign_suffixes:
            for path in benign_paths[:2]:
                samples.append(
                    {
                        "text": f"{root}{idx}.{suffix}{path}",
                        "label": "benign",
                        "sample_type": "bootstrap",
                    }
                )

    for idx, base in enumerate(malicious_bases, 1):
        for tld in malicious_tlds:
            for path in malicious_paths[:2]:
                samples.append(
                    {
                        "text": f"{base}-{idx}.{tld}{path}",
                        "label": "malicious",
                        "sample_type": "bootstrap",
                    }
                )

    extras = [
        "verify-security-login.top",
        "secure-paypal-update.xyz/login",
        "microsoft-support-check.live/auth",
        "banking-alert-verify.icu/account",
        "cloud-auth-center.click/verify",
        "mail-sso-portal.pw/login",
    ]
    for item in extras:
        samples.append({"text": item, "label": "malicious", "sample_type": "bootstrap"})

    return samples
