"""
历史沿革模板加载与渲染模块
支持从外部txt文件加载模板，使用Handlebars风格语法
支持多股东合并显示
"""
import os
import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# 模板文件目录
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "template")


@dataclass
class TemplateVariable:
    """模板变量定义"""
    name: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class HistoryTemplate:
    """历史沿革模板"""
    name: str
    content: str
    variables: List[TemplateVariable] = field(default_factory=list)
    
    def render(self, data: Dict[str, Any]) -> str:
        """渲染模板"""
        # 先处理数据，为空值添加占位符
        processed_data = self._process_placeholders(data)
        
        result = self.content
        
        # 处理 each 循环
        result = self._render_each(result, processed_data)
        
        # 处理 if 条件
        result = self._render_if(result, processed_data)
        
        # 处理简单变量替换
        result = self._render_variables(result, processed_data)
        
        # 处理 unless 条件
        result = self._render_unless(result, processed_data)
        
        # 清理多余的百分号（因为模板中已有%）
        result = result.replace("【**%】%", "【**%】")
        
        return result
    
    def _process_placeholders(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理占位符：空值替换为【**单位】格式"""
        processed = {}
        
        for key, value in data.items():
            if isinstance(value, list):
                processed[key] = []
                for item in value:
                    if isinstance(item, dict):
                        processed_item = {}
                        for k, v in item.items():
                            processed_item[k] = self._format_placeholder(k, v)
                        processed[key].append(processed_item)
                    else:
                        processed[key].append(item)
            elif isinstance(value, dict):
                processed[key] = {}
                for k, v in value.items():
                    processed[key][k] = self._format_placeholder(k, v)
            else:
                processed[key] = self._format_placeholder(key, value)
        
        return processed
    
    def _format_placeholder(self, key: str, value: Any) -> str:
        """根据字段类型格式化占位符"""
        if value and str(value).strip():
            return str(value)
        
        # 根据字段名判断占位符类型
        if 'ratio' in key.lower() or '比例' in key:
            return "【**】"  # 模板中已有 % 符号
        elif 'capital' in key.lower() or 'amount' in key.lower() or '万元' in key or '金额' in key or '价格' in key or 'price' in key.lower():
            return "【**】"  # 模板中已有 万元 单位
        elif 'date' in key.lower() or '日期' in key:
            return "【**年**月**日】"
        elif 'name' in key.lower() or '姓名' in key or '名称' in key:
            return "【**】"
        else:
            return "【**】"
    
    def _render_each(self, template: str, data: Dict[str, Any]) -> str:
        """渲染 {{#each items}}...{{/each}} 循环"""
        pattern = r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}'
        
        def replace_each(match):
            list_name = match.group(1)
            inner_template = match.group(2)
            
            items = data.get(list_name, [])
            if not items:
                return ""
            
            results = []
            for i, item in enumerate(items):
                item_data = dict(data)
                item_data.update(item)
                item_data['@index'] = i + 1
                item_data['@last'] = (i == len(items) - 1)
                
                item_result = inner_template
                # 替换当前项的变量
                for key, value in item.items():
                    item_result = item_result.replace(f'{{{{{key}}}}}', str(value))
                # 替换内置变量
                item_result = item_result.replace('{{@index}}', str(i + 1))
                
                # 处理 unless @last
                item_result = self._render_unless_last(item_result, i == len(items) - 1)
                
                results.append(item_result)
            
            return ''.join(results)
        
        return re.sub(pattern, replace_each, template, flags=re.DOTALL)
    
    def _render_unless(self, template: str, data: Dict[str, Any]) -> str:
        """渲染 {{#unless condition}}...{{/unless}} 条件"""
        return template
    
    def _render_unless_last(self, template: str, is_last: bool) -> str:
        """处理 {{#unless @last}}...{{/unless}}"""
        if is_last:
            return re.sub(r'\{\{#unless\s+@last\}\}.*?\{\{/unless\}\}', '', template)
        else:
            return re.sub(r'\{\{#unless\s+@last\}\}(.*?)\{\{/unless\}\}', r'\1', template)
    
    def _render_if(self, template: str, data: Dict[str, Any]) -> str:
        """渲染 {{#if condition}}...{{/if}} 条件"""
        pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
        
        def replace_if(match):
            var_name = match.group(1)
            inner_content = match.group(2)
            
            if data.get(var_name):
                return inner_content
            else:
                return ""
        
        return re.sub(pattern, replace_if, template, flags=re.DOTALL)
    
    def _render_variables(self, template: str, data: Dict[str, Any]) -> str:
        """渲染简单变量 {{variable}}"""
        result = template
        
        # 匹配所有 {{variable}} 格式的变量
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, result)
        
        for var_name in matches:
            if var_name in data:
                value = str(data[var_name])
                result = result.replace(f'{{{{{var_name}}}}}', value)
        
        return result


class TemplateLoader:
    """模板加载器"""
    
    TEMPLATE_FILES = {
        'equity_transfer': '股权转让模板文件 (equity_transfer_template.txt).txt',
        'capital_increase': '增资模板文件 (capital_increase_template.txt).txt',
        'capital_reduction': '减资模板文件 (capital_reduction_template.txt).txt',
    }
    
    def __init__(self, template_dir: str = TEMPLATE_DIR):
        self.template_dir = template_dir
        self._cache: Dict[str, HistoryTemplate] = {}
    
    def load_template(self, template_name: str) -> Optional[HistoryTemplate]:
        """加载指定模板"""
        if template_name in self._cache:
            return self._cache[template_name]
        
        filename = self.TEMPLATE_FILES.get(template_name)
        if not filename:
            raise ValueError(f"未知的模板名称: {template_name}")
        
        filepath = os.path.join(self.template_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"模板文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        template = HistoryTemplate(
            name=template_name,
            content=content,
            variables=self._extract_variables(content)
        )
        
        self._cache[template_name] = template
        return template
    
    def _extract_variables(self, content: str) -> List[TemplateVariable]:
        """从模板内容中提取变量定义"""
        variables = []
        simple_vars = re.findall(r'\{\{(\w+)\}\}', content)
        
        seen = set()
        for var_name in simple_vars:
            if var_name not in seen and not var_name.startswith('@'):
                seen.add(var_name)
                variables.append(TemplateVariable(name=var_name, description="", required=True))
        
        return variables
    
    def reload_template(self, template_name: str) -> HistoryTemplate:
        """重新加载模板"""
        if template_name in self._cache:
            del self._cache[template_name]
        return self.load_template(template_name)


# 全局模板加载器实例
template_loader = TemplateLoader()


def render_equity_transfer(data: Dict[str, Any]) -> str:
    """渲染股权转让模板"""
    template = template_loader.load_template('equity_transfer')
    return template.render(data)


def render_capital_increase(data: Dict[str, Any]) -> str:
    """渲染增资模板"""
    template = template_loader.load_template('capital_increase')
    return template.render(data)


def render_capital_reduction(data: Dict[str, Any]) -> str:
    """渲染减资模板"""
    template = template_loader.load_template('capital_reduction')
    return template.render(data)


if __name__ == "__main__":
    # 测试
    equity_data = {
        "meeting_date": "2020年8月14日",
        "registration_date": "2020年9月16日",
        "company_name": "道通智能有限",
        "transfers": [
            {"transferor": "钟艳萍", "transferee": "徐万宝", "ratio": "", "capital": "", "price": ""}
        ],
        "shareholders_after_transfer": [
            {"name": "李红京", "amount": "43,260.8221", "ratio": "51.4647"}
        ],
        "total_capital": "84,059.1737"
    }
    
    print("=" * 50)
    print("股权转让模板渲染结果:")
    print("=" * 50)
    result = render_equity_transfer(equity_data)
    print(result)
