import React from 'react';

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function YamlEditor({ value, onChange, placeholder }: Props) {
  return (
    <textarea
      className="w-full h-64 bg-slate-900 border border-slate-700 rounded-md p-4 font-mono text-sm text-slate-300 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-y"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      spellCheck={false}
    />
  );
}
