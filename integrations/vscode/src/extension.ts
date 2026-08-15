/**
 * llm-wiki VS Code extension — minimal scaffold.
 *
 * Provides:
 *  - "Open llm-wiki" command (opens site/index.html in the default browser)
 *  - "Sync Sessions" command (runs `python3 -m llmwiki sync`)
 *  - "Build Site" command (runs `python3 -m llmwiki build`)
 *  - Sidebar tree view listing wiki pages by section
 */

import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { exec } from "child_process";

// ---------------------------------------------------------------------------
// Activation
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration("llmwiki");
  const python = config.get<string>("pythonPath", "python3");

  // Command: Open llm-wiki in browser. The built site is plain files, so
  // it opens straight from disk with nothing running.
  context.subscriptions.push(
    vscode.commands.registerCommand("llmwiki.openSite", () => {
      const root = vscode.workspace.workspaceFolders?.[0];
      if (!root) {
        vscode.window.showErrorMessage("llm-wiki: open a workspace folder first.");
        return;
      }
      const home = vscode.Uri.joinPath(root.uri, "site", "index.html");
      if (!fs.existsSync(home.fsPath)) {
        vscode.window.showErrorMessage(
          `llm-wiki: ${home.fsPath} not found — run "Build Site" first.`
        );
        return;
      }
      vscode.env.openExternal(home);
    })
  );

  // Command: Sync sessions
  context.subscriptions.push(
    vscode.commands.registerCommand("llmwiki.sync", () => {
      runLlmwikiCommand(python, "sync", "Syncing sessions...");
    })
  );

  // Command: Build site
  context.subscriptions.push(
    vscode.commands.registerCommand("llmwiki.build", () => {
      runLlmwikiCommand(python, "build", "Building site...");
    })
  );

  // Sidebar tree view
  const wikiRoot = findWikiRoot();
  if (wikiRoot) {
    const treeProvider = new WikiTreeProvider(wikiRoot);
    vscode.window.registerTreeDataProvider("llmwikiPages", treeProvider);

    // Refresh tree after sync/build
    context.subscriptions.push(
      vscode.commands.registerCommand("llmwiki.refreshTree", () => {
        treeProvider.refresh();
      })
    );
  }
}

export function deactivate() {
  // Nothing to clean up.
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function findWikiRoot(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders) return undefined;
  for (const folder of folders) {
    const candidate = path.join(folder.uri.fsPath, "wiki");
    if (fs.existsSync(path.join(candidate, "index.md"))) {
      return candidate;
    }
  }
  return undefined;
}

function runLlmwikiCommand(python: string, subcommand: string, msg: string) {
  const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!cwd) {
    vscode.window.showErrorMessage(
      "llm-wiki: No workspace folder open."
    );
    return;
  }

  vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: msg,
      cancellable: false,
    },
    () =>
      new Promise<void>((resolve, reject) => {
        exec(
          `${python} -m llmwiki ${subcommand}`,
          { cwd },
          (err, stdout, stderr) => {
            if (err) {
              vscode.window.showErrorMessage(
                `llm-wiki ${subcommand} failed: ${stderr || err.message}`
              );
              reject(err);
            } else {
              vscode.window.showInformationMessage(
                `llm-wiki ${subcommand} complete.`
              );
              vscode.commands.executeCommand("llmwiki.refreshTree");
              resolve();
            }
          }
        );
      })
  );
}

// ---------------------------------------------------------------------------
// Tree View Provider
// ---------------------------------------------------------------------------

type WikiSection = "sources" | "entities" | "concepts" | "syntheses";

const SECTIONS: WikiSection[] = [
  "sources",
  "entities",
  "concepts",
  "syntheses",
];

class WikiTreeProvider implements vscode.TreeDataProvider<WikiTreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<
    WikiTreeItem | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private wikiRoot: string) {}

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: WikiTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: WikiTreeItem): WikiTreeItem[] {
    if (!element) {
      // Top-level: one node per section
      return SECTIONS.map(
        (s) =>
          new WikiTreeItem(
            s,
            vscode.TreeItemCollapsibleState.Collapsed,
            path.join(this.wikiRoot, s)
          )
      );
    }

    // Children: .md files inside the section folder
    const dir = element.fsPath;
    if (!dir || !fs.existsSync(dir)) return [];

    return fs
      .readdirSync(dir)
      .filter((f) => f.endsWith(".md") && !f.startsWith("_"))
      .sort()
      .map((f) => {
        const item = new WikiTreeItem(
          f.replace(/\.md$/, ""),
          vscode.TreeItemCollapsibleState.None,
          path.join(dir, f)
        );
        item.command = {
          command: "vscode.open",
          title: "Open Page",
          arguments: [vscode.Uri.file(path.join(dir, f))],
        };
        return item;
      });
  }
}

class WikiTreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly fsPath: string
  ) {
    super(label, collapsibleState);
    this.tooltip = fsPath;
  }
}
