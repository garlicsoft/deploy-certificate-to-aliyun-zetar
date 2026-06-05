import datetime
import os
from aliyunsdkcore.client import AcsClient
from aliyunsdkcdn.request.v20180510 import SetCdnDomainSSLCertificateRequest

def get_env_var(key):
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Environment variable {key} not set")
    return value

def file_exists_and_not_empty(file_path):
    expanded_path = os.path.expanduser(file_path)
    return os.path.isfile(expanded_path) and os.path.getsize(expanded_path) > 0

def match_root_domain(cdn_domain, domains):
    """根据 CDN 加速域名匹配对应的根域名（DOMAINS 中的项）。"""
    cdn_domain = cdn_domain.strip()
    matches = [d.strip() for d in domains if cdn_domain == d.strip() or cdn_domain.endswith('.' + d.strip())]
    if not matches:
        raise ValueError(f"CDN 域名 {cdn_domain} 无法匹配 DOMAINS 中的任何根域名: {domains}")
    return max(matches, key=len)

def upload_certificate(client, cdn_domain, root_domain, cert_path, key_path):
    expanded_cert_path = os.path.expanduser(cert_path)
    expanded_key_path = os.path.expanduser(key_path)

    if not file_exists_and_not_empty(expanded_cert_path) or not file_exists_and_not_empty(expanded_key_path):
        raise FileNotFoundError(f"Certificate or key file for domain {root_domain} is missing or empty")
    
    with open(expanded_cert_path, 'r') as f:
        cert = f.read()

    with open(expanded_key_path, 'r') as f:
        key = f.read()

    cert_date = datetime.datetime.now().strftime("%Y%m%d")
    cert_name = root_domain + cert_date

    request = SetCdnDomainSSLCertificateRequest.SetCdnDomainSSLCertificateRequest()
    # CDN 加速域名
    request.set_DomainName(cdn_domain)
    # 证书名称：使用根域名 + 日期，而非 CDN 子域名
    request.set_CertName(cert_name)
    request.set_CertType('upload')
    request.set_SSLProtocol('on')
    request.set_SSLPub(cert)
    request.set_SSLPri(key)
    request.set_CertRegion('cn-hangzhou')

    response = client.do_action_with_exception(request)
    print(f"已部署: CDN={cdn_domain}, 证书名={cert_name}, 根域名={root_domain}")
    print(str(response, encoding='utf-8'))

def main():
    access_key_id = get_env_var('ALIYUN_CDN_ACCESS_KEY_ID')
    access_key_secret = get_env_var('ALIYUN_CDN_ACCESS_KEY_SECRET')
    domains = get_env_var('DOMAINS').split(',')
    cdn_domains = get_env_var('ALIYUN_CDN_DOMAINS').split(',')

    client = AcsClient(access_key_id, access_key_secret, 'cn-hangzhou')

    for cdn_domain in cdn_domains:
        cdn_domain = cdn_domain.strip()
        if not cdn_domain:
            continue
        root_domain = match_root_domain(cdn_domain, domains)
        cert_path = f'~/certs/{root_domain}/fullchain.pem'
        key_path = f'~/certs/{root_domain}/privkey.pem'
        upload_certificate(client, cdn_domain, root_domain, cert_path, key_path)

if __name__ == "__main__":
    main()