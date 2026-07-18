import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "一只鱼律 · 历史沿革生成器",
  description: "上传企查查报告，一键生成公司历史沿革（股权转让 / 增资 / 减资）",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
