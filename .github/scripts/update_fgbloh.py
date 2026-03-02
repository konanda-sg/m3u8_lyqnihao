#!/usr/bin/env python3
"""
FGBLH 作者仓库同步脚本

功能：
1. 跟踪 https://github.com/FGBLH 的 3 个仓库（FG, fgrjk, fgrjk2）
2. 自动检查内容更新
3. 将更新的文件复制到对应目录
4. 同名文件有更新时覆盖
5. 作者删除文件或内容被清空时，保留原文件不动
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple

# FGBLH 的 3 个仓库配置
REPOS = [
    {"name": "FG", "url": "https://github.com/FGBLH/FG.git"},
    {"name": "fgrjk", "url": "https://github.com/FGBLH/fgrjk.git"},
    {"name": "fgrjk2", "url": "https://github.com/FGBLH/fgrjk2.git"},
]

def git_clone_or_pull(repo_url: str, repo_dir: str) -> Tuple[bool, str]:
    """
    克隆或拉取仓库

    参数：
    - repo_url: 仓库 URL
    - repo_dir: 本地存储目录

    返回值：
    - (True, None): 成功
    - (False, 错误信息): 失败
    """
    if os.path.exists(repo_dir):
        # 仓库已存在，拉取最新代码
        print(f"[{repo_dir}] 仓库已存在，正在拉取更新...")
        try:
            result = subprocess.run(
                ["git", "-C", repo_dir, "fetch", "origin"],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return False, f"git fetch 失败: {result.stderr}"
            # 检查是否有更新
            result = subprocess.run(
                ["git", "-C", repo_dir, "log", "--oneline", "HEAD..origin/main"],
                capture_output=True,
                text=True
            )
            has_updates = result.stdout.strip() != ""
            if has_updates:
                result = subprocess.run(
                    ["git", "-C", repo_dir, "reset", "--hard", "origin/main"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    return False, f"git reset 失败: {result.stderr}"
                print(f"[{repo_dir}] ✓ 已拉取更新")
                return True, None
            else:
                print(f"[{repo_dir}] - 无更新")
                return False, "无更新"
        except Exception as e:
            return False, f"拉取失败: {e}"
    else:
        # 仓库不存在，克隆
        print(f"[{repo_dir}] 仓库不存在，正在克隆...")
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, repo_dir],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, f"克隆失败: {result.stderr}"
            print(f"[{repo_dir}] ✓ 克隆成功")
            return True, None
        except Exception as e:
            return False, f"克隆失败: {e}"

def sync_files(src_dir: str, dst_dir: str) -> Tuple[int, str]:
    """
    同步文件：将源目录的文件复制到目标目录

    规则：
    - 同名文件有更新时覆盖
    - 作者删除的文件保留原文件不动
    - 内容被清空的文件保留原文件不动

    参数：
    - src_dir: 源目录（从作者仓库克隆的临时目录）
    - dst_dir: 目标目录（FGBLH/仓库名）

    返回值：
    - (更新的文件数, 消息)
    """
    if not os.path.exists(src_dir):
        return 0, f"源目录不存在: {src_dir}"

    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)

    updated_count = 0
    updated_files = []

    # 遍历源目录中的所有文件
    for root, dirs, files in os.walk(src_dir):
        # 跳过 .git 目录
        if '.git' in root:
            continue

        for file in files:
            src_file = os.path.join(root, file)
            # 计算相对路径
            rel_path = os.path.relpath(src_file, src_dir)
            dst_file = os.path.join(dst_dir, rel_path)

            # 确保目标目录存在
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)

            # 检查文件是否需要更新
            should_update = False
            if not os.path.exists(dst_file):
                # 目标文件不存在，需要创建
                should_update = True
            else:
                # 目标文件存在，检查是否需要更新
                try:
                    src_size = os.path.getsize(src_file)
                    dst_size = os.path.getsize(dst_file)
                    src_mtime = os.path.getmtime(src_file)
                    dst_mtime = os.path.getmtime(dst_file)

                    # 如果源文件大小为 0，不更新（避免覆盖原有内容）
                    if src_size == 0:
                        print(f"  跳过空文件: {rel_path}")
                        continue

                    # 如果源文件更新或大小不同，需要更新
                    if src_mtime > dst_mtime or src_size != dst_size:
                        should_update = True
                except Exception as e:
                    print(f"  警告：无法比较文件 {rel_path}: {e}")
                    should_update = True

            if should_update:
                try:
                    shutil.copy2(src_file, dst_file)
                    updated_count += 1
                    updated_files.append(rel_path)
                    print(f"  ✓ 更新: {rel_path}")
                except Exception as e:
                    print(f"  ✗ 复制失败 {rel_path}: {e}")

    return updated_count, ", ".join(updated_files[:3])

def clean_temp_dirs() -> None:
    """清理临时克隆的仓库目录"""
    temp_dir = "/tmp/FGBLH_temp"
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            print(f"已清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"清理临时目录失败: {e}")

def main():
    """主函数"""
    # 设置临时目录
    temp_base = "/tmp/FGBLH_temp"
    os.makedirs(temp_base, exist_ok=True)

    total_updated = 0
    results = []

    # 处理每个仓库
    for repo in REPOS:
        repo_name = repo["name"]
        repo_url = repo["url"]
        temp_repo_dir = os.path.join(temp_base, repo_name)
        dst_dir = os.path.join("FGBLH", repo_name)

        print(f"\n{'='*60}")
        print(f"处理仓库: {repo_name}")
        print(f"{'='*60}")

        # 克隆或拉取仓库
        success, msg = git_clone_or_pull(repo_url, temp_repo_dir)
        if not success:
            if msg == "无更新":
                results.append((repo_name, 0, "无更新"))
                continue
            else:
                print(f"[{repo_name}] ✗ 错误: {msg}")
                results.append((repo_name, 0, f"错误: {msg}"))
                continue

        # 同步文件
        updated_count, updated_files = sync_files(temp_repo_dir, dst_dir)
        total_updated += updated_count

        if updated_count > 0:
            print(f"[{repo_name}] ✓ 已更新 {updated_count} 个文件")
            results.append((repo_name, updated_count, updated_files))
        else:
            print(f"[{repo_name}] - 无文件需要更新")
            results.append((repo_name, 0, "无更新"))

    # 输出总结
    print(f"\n{'='*60}")
    print("同步完成总结")
    print(f"{'='*60}")
    for repo_name, count, msg in results:
        status = "✓" if count > 0 else "-"
        print(f"{status} {repo_name}: {count} 个文件更新 - {msg}")

    print(f"\n总计更新: {total_updated} 个文件")

    # 清理临时目录
    clean_temp_dirs()

    # 如果有更新，返回 0；否则返回 1（用于 GitHub Actions 判断）
    return 0 if total_updated > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
