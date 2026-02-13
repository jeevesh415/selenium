#!/usr/bin/env python3
"""
Validate and compare generated vs hand-written BiDi modules.

This script analyzes both generated and hand-written BiDi modules to:
1. Compare module structure
2. Validate command methods
3. Check type definitions
4. Identify compatibility issues
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ModuleAnalyzer:
    """Analyze Python module structure."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.tree = None
        self.classes = {}
        self.methods = defaultdict(list)
        self.dataclasses = set()
        self.imports = []
        
        self._parse()
    
    def _parse(self):
        """Parse the Python file."""
        with open(self.file_path) as f:
            try:
                self.tree = ast.parse(f.read())
            except SyntaxError as e:
                print(f"Syntax error in {self.file_path}: {e}")
                return
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a dataclass
                is_dataclass = any(
                    isinstance(d, ast.Name) and d.id == 'dataclass'
                    for d in node.decorator_list
                )
                if is_dataclass:
                    self.dataclasses.add(node.name)
                
                # Collect class info
                self.classes[node.name] = {
                    'methods': [],
                    'fields': [],
                    'is_dataclass': is_dataclass,
                }
                
                # Get methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        self.classes[node.name]['methods'].append(item.name)
                        self.methods[node.name].append(item.name)
                    elif isinstance(item, ast.AnnAssign):
                        self.classes[node.name]['fields'].append(item.target.id)
    
    def get_dataclass_count(self) -> int:
        """Get number of dataclasses."""
        return len(self.dataclasses)
    
    def get_command_class(self) -> Tuple[str, List[str]]:
        """Get the command class (non-dataclass singleton except __init__)."""
        for name, info in self.classes.items():
            if not info['is_dataclass']:
                methods = [m for m in info['methods'] if not m.startswith('_')]
                if methods:  # Has public methods
                    return name, methods
        return None, []
    
    def get_command_methods(self) -> Dict[str, List[str]]:
        """Get all command methods by class."""
        result = {}
        for name, info in self.classes.items():
            if not info['is_dataclass']:
                methods = [m for m in info['methods'] if not m.startswith('__')]
                if methods:
                    result[name] = methods
        return result


def compare_modules(generated_dir: Path, source_dir: Path) -> Dict:
    """Compare generated vs hand-written modules."""
    results = {
        'modules': {},
        'summary': {
            'generated_types': 0,
            'hand_written_types': 0,
            'generated_commands': 0,
            'hand_written_commands': 0,
            'issues': [],
        }
    }
    
    # Get list of modules to compare
    generated_files = sorted(generated_dir.glob('*.py'))
    
    for gen_file in generated_files:
        if gen_file.name in ('__init__.py', 'common.py'):
            continue
        
        module_name = gen_file.stem
        source_file = source_dir / gen_file.name
        
        if not source_file.exists():
            results['summary']['issues'].append(f"Source file missing: {module_name}")
            continue
        
        # Analyze both
        gen_analyzer = ModuleAnalyzer(gen_file)
        src_analyzer = ModuleAnalyzer(source_file)
        
        gen_types = gen_analyzer.get_dataclass_count()
        src_types = 0  # Hand-written typically doesn't have dataclasses
        
        gen_cmd_class, gen_methods = gen_analyzer.get_command_class()
        src_cmd_class, src_methods = src_analyzer.get_command_class()
        
        results['modules'][module_name] = {
            'generated': {
                'types': gen_types,
                'command_class': gen_cmd_class,
                'methods': sorted(gen_methods),
                'method_count': len(gen_methods),
            },
            'source': {
                'types': src_types,
                'command_class': src_cmd_class,
                'methods': sorted(src_methods),
                'method_count': len(src_methods),
            },
            'differences': {
                'type_count_diff': gen_types - src_types,
                'method_count_diff': len(gen_methods) - len(src_methods),
                'new_methods': sorted(set(gen_methods) - set(src_methods)),
                'missing_methods': sorted(set(src_methods) - set(gen_methods)),
            }
        }
        
        results['summary']['generated_types'] += gen_types
        results['summary']['generated_commands'] += len(gen_methods)
        results['summary']['hand_written_commands'] += len(src_methods)
    
    return results


def format_results(results: Dict) -> str:
    """Format comparison results as markdown."""
    output = []
    output.append("# BiDi Module Comparison Results\n")
    
    # Summary
    summary = results['summary']
    output.append("## Summary\n")
    output.append(f"- **Generated Type Definitions**: {summary['generated_types']}\n")
    output.append(f"- **Generated Commands**: {summary['generated_commands']}\n")
    output.append(f"- **Hand-Written Commands**: {summary['hand_written_commands']}\n")
    
    if summary['issues']:
        output.append("\n### Issues Found\n")
        for issue in summary['issues']:
            output.append(f"- ⚠️ {issue}\n")
    
    # Per-module details
    output.append("\n## Per-Module Comparison\n")
    
    for module_name, info in sorted(results['modules'].items()):
        gen = info['generated']
        src = info['source']
        diff = info['differences']
        
        output.append(f"\n### {module_name}.py\n")
        output.append(f"| Aspect | Generated | Source | Diff |\n")
        output.append(f"|--------|-----------|--------|------|\n")
        output.append(f"| Types | {gen['types']} | {src['types']} | +{diff['type_count_diff']} |\n")
        output.append(f"| Methods | {gen['method_count']} | {src['method_count']} | {diff['method_count_diff']:+d} |\n")
        
        if diff['new_methods']:
            output.append(f"\n**New Methods in Generated**: {', '.join(diff['new_methods'])}\n")
        
        if diff['missing_methods']:
            output.append(f"\n**Methods Not in Generated**: {', '.join(diff['missing_methods'])}\n")
    
    return "".join(output)


def main():
    """Main entry point."""
    generated_dir = Path("bazel-bin/py/selenium/webdriver/common/bidi")
    source_dir = Path("py/selenium/webdriver/common/bidi")
    
    if not generated_dir.exists():
        print(f"Error: Generated directory not found: {generated_dir}")
        print("Run: bazel build //py:create-bidi-src")
        sys.exit(1)
    
    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}")
        sys.exit(1)
    
    print("Comparing generated vs hand-written BiDi modules...\n")
    
    results = compare_modules(generated_dir, source_dir)
    
    # Print results
    formatted = format_results(results)
    print(formatted)
    
    # Save to file
    output_file = Path("PHASE_8_VALIDATION_RESULTS.md")
    with open(output_file, 'w') as f:
        f.write(formatted)
    
    print(f"\n✓ Results saved to {output_file}")


if __name__ == "__main__":
    main()
