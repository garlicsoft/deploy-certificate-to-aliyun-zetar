import datetime
import json
import os
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdkcore.client import AcsClient
from aliyunsdkcdn.request.v20180510 import DescribeCdnCertificateDetailRequest
from aliyunsdkcdn.request.v20180510 import SetCdnDomainSSLCertificateRequest

CERT_REGION = 'cn-hangzhou'

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

def read_cert_files(cert_path, key_path, root_domain):
    expanded_cert_path = os.path.expanduser(cert_path)
    expanded_key_path = os.path.expanduser(key_path)

    if not file_exists_and_not_empty(expanded_cert_path) or not file_exists_and_not_empty(expanded_key_path):
        raise FileNotFoundError(f"Certificate or key file for domain {root_domain} is missing or empty")

    with open(expanded_cert_path, 'r') as f:
        cert = f.read()

    with open(expanded_key_path, 'r') as f:
        key = f.read()

    return cert, key

def get_cert_id_by_name(client, cert_name):
    request = DescribeCdnCertificateDetailRequest.DescribeCdnCertificateDetailRequest()
    request.set_CertName(cert_name)
    response = client.do_action_with_exception(request)
    data = json.loads(response)
    cert_id = data.get('CertId')
    if not cert_id:
        raise RuntimeError(f"无法查询证书 ID，CertName={cert_name}")
    return cert_id

def upload_and_bind(client, cdn_domain, cert_name, cert, key):
    request = SetCdnDomainSSLCertificateRequest.SetCdnDomainSSLCertificateRequest()
    request.set_DomainName(cdn_domain)
    request.set_CertName(cert_name)
    request.set_CertType('upload')
    request.set_SSLProtocol('on')
    request.set_SSLPub(cert)
    request.set_SSLPri(key)
    request.set_CertRegion(CERT_REGION)
    response = client.do_action_with_exception(request)
    print(str(response, encoding='utf-8'))

def bind_existing_cert(client, cdn_domain, cert_name, cert_id):
    request = SetCdnDomainSSLCertificateRequest.SetCdnDomainSSLCertificateRequest()
    request.set_DomainName(cdn_domain)
    request.set_CertName(cert_name)
    request.set_CertId(cert_id)
    request.set_CertType('cas')
    request.set_SSLProtocol('on')
    request.set_CertRegion(CERT_REGION)
    response = client.do_action_with_exception(request)
    print(str(response, encoding='utf-8'))

def is_cert_already_uploaded_error(error):
    if not isinstance(error, ServerException):
        return False
    error_code = error.get_error_code()
    return error_code in ('CertNameAlreadyExists', 'CertificateContent.Duplicated', 'Certificate.Duplicated')

def deploy_certificate(client, cdn_domain, root_domain, cert_path, key_path, cert_name, uploaded_certs):
    cert, key = read_cert_files(cert_path, key_path, root_domain)

    if root_domain in uploaded_certs:
        cert_id = uploaded_certs[root_domain]
        bind_existing_cert(client, cdn_domain, cert_name, cert_id)
        print(f"已绑定: CDN={cdn_domain}, 证书名={cert_name}, 根域名={root_domain}, CertId={cert_id}")
        return

    try:
        upload_and_bind(client, cdn_domain, cert_name, cert, key)
    except ServerException as error:
        if not is_cert_already_uploaded_error(error):
            raise
        cert_id = get_cert_id_by_name(client, cert_name)
        bind_existing_cert(client, cdn_domain, cert_name, cert_id)
        uploaded_certs[root_domain] = cert_id
        print(f"已绑定(证书已存在): CDN={cdn_domain}, 证书名={cert_name}, 根域名={root_domain}, CertId={cert_id}")
        return

    cert_id = get_cert_id_by_name(client, cert_name)
    uploaded_certs[root_domain] = cert_id
    print(f"已上传: CDN={cdn_domain}, 证书名={cert_name}, 根域名={root_domain}, CertId={cert_id}")

def main():
    access_key_id = get_env_var('ALIYUN_CDN_ACCESS_KEY_ID')
    access_key_secret = get_env_var('ALIYUN_CDN_ACCESS_KEY_SECRET')
    domains = get_env_var('DOMAINS').split(',')
    cdn_domains = get_env_var('ALIYUN_CDN_DOMAINS').split(',')
    cert_date = datetime.datetime.now().strftime("%Y%m%d")

    client = AcsClient(access_key_id, access_key_secret, CERT_REGION)
    uploaded_certs = {}

    for cdn_domain in cdn_domains:
        cdn_domain = cdn_domain.strip()
        if not cdn_domain:
            continue
        root_domain = match_root_domain(cdn_domain, domains)
        cert_name = root_domain + cert_date
        cert_path = f'~/certs/{root_domain}/fullchain.pem'
        key_path = f'~/certs/{root_domain}/privkey.pem'
        deploy_certificate(client, cdn_domain, root_domain, cert_path, key_path, cert_name, uploaded_certs)

if __name__ == "__main__":
    main()
