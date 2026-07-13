{# templates/equity_transfer/batch_transfer.tpl #}
{{ date }}，{{ company_name }}召开股东会并作出决议，同意：
{%- for group in transfer_groups %}
{{ loop.index }}.{% for item in group.items %}{% if not loop.first %}，{% endif %}股东{{ item.from }}将其占{{ company_name }}{{ item.ratio }}%股权转让给{{ item.to }}{% endfor %}；{% endfor %}
其他股东自愿放弃优先购买权。

{{ contract_date }}，{% for group in transfer_groups %}{% for signer in group.signers %}{{ signer.from }}与{{ signer.to }}{% if not loop.last %}、{% endif %}{% endfor %}就上述股权转让事宜签署了《股权转让合同》{% if not loop.last %}；同日，{% else %}。{% endif %}{% endfor %}上述股权转让的背景系为{{ background_purpose }}，{% for desc in pricing_descriptions %}{{ desc }}{% if not loop.last %}；{% endif %}{% endfor %}。

{{ registration_date }}，{{ company_name }}就上述事宜在{{ registry }}办理了工商变更登记手续。

本次股权转让完成后，{{ company_name }}的股权结构如下：