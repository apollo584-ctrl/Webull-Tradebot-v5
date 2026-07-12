# GitHub Setup Handoff

This document contains only the GitHub CLI workflow.

## Rules

- GitHub actions apply only to the explicitly current project.
- Never infer the push target from this guide or another project.
- Bind the current folder, origin, and default branch once; later helper commands verify them automatically.
- Never stage secrets, credentials, runtime data, databases, or unrelated changes.
- Use draft pull requests by default.
- Never force-push, hard-reset, delete branches, or overwrite an unexpected remote.

## One-Time Binding

From the explicitly current project:

    pr.bat bind

The helper displays the current folder, origin remote, and GitHub default branch. Type YES once to save the local binding.

## Authentication

    gh auth login -h github.com --web
    gh auth status

Never paste or expose tokens.

## New Repository

After confirming the current project and exact repository name:

    gh repo create OWNER/REPOSITORY --private --source . --remote origin
    git branch -M main
    git push -u origin main
    gh repo edit OWNER/REPOSITORY --default-branch main

Use --public only when explicitly requested.

## Pull Request Workflow

    pr.bat start feature-name
    pr.bat status
    pr.bat finish "Commit and PR title"

The finish command verifies the saved project binding, shows changed files, requires YES, blocks sensitive paths, commits, pushes the current branch, and opens a draft PR against main.

## Completion Report

Record the current project folder, repository URL, branch, commit, default branch, PR URL, checks run, and anything blocked.