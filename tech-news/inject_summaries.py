#!/usr/bin/env python3
"""Inject InfoQ summaries into tech-news/index.html for each article."""
import re
from html import escape as he
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_HTML = SCRIPT_DIR / "index.html"

# (url_fragment, summary, infoq_yes: bool, infoq_reason)
SUMMARIES = [
    (
        "docker-hardened-images-one-year-later",
        "Docker Hardened Images (DHI) celebrates its one-year milestone with 500k daily pulls and 2,000+ hardened images, with multi-distro builds (Debian and Alpine), from-source packages, and comprehensive cryptographic attestations—all freely available to developers.",
        True,
        "Directly addresses software supply chain security, DevOps containerization strategy, and base-image architectural decisions that impact production systems and compliance.",
    ),
    (
        "analyze-hugging-face-for-arm64-readiness",
        "Demonstrates how Docker's MCP Toolkit with the Arm MCP Server can automatically scan Hugging Face Spaces for Arm64 compatibility in ~15 minutes, surfacing blockers like hardcoded x86_64 wheel URLs and actionable fixes without manual investigation.",
        True,
        "Covers multi-architecture container support, AI/ML deployment on Arm (Graviton, Apple Silicon), and AI-assisted tooling for compatibility analysis—squarely in InfoQ's DevOps and AI/ML territory.",
    ),
    (
        "simplifying-terraform-dynamic-credentials-on-aws-with-native-oidc-integration",
        "Covers how to configure Terraform's Dynamic Provider Credentials using OIDC directly with AWS without requiring HCP Terraform, simplifying cloud authentication and eliminating long-lived static credentials.",
        True,
        "Highly relevant for InfoQ DevOps and cloud architecture readers who manage multi-cloud credential security and infrastructure-as-code workflows.",
    ),
    (
        "nodeweekly.com/issues/619",
        "Node Weekly issue 619 highlights social engineering attacks targeting high-impact Node.js maintainers to compromise critical packages in the ecosystem, with practical guidance on account security and supply-chain hygiene.",
        True,
        "Supply chain attacks on widely-used open source maintainers are a critical security topic for InfoQ's software engineering and DevOps audience.",
    ),
    (
        "smarter-vulnerability-prioritization-with-docker-and-mend-io",
        "Announces the Mend.io and Docker Hardened Images integration, which uses VEX statements to distinguish exploitable from non-exploitable CVEs in container images, allowing developers to focus on genuine risks rather than noise.",
        True,
        "Addresses software supply chain security, DevOps practices, and container security governance—core concerns for engineers building and deploying containerized systems at scale.",
    ),
    (
        "defending-your-software-supply-chain",
        "Outlines a strategy for defending against software supply chain attacks by replacing implicit trust with explicit verification across base images, CI/CD pipelines, developer endpoints, and AI agent execution environments, including specific practices like SLSA attestations and credential cooldown periods.",
        True,
        "Essential reading for architects and platform engineers designing secure development workflows, covering supply chain security, CI/CD hardening, and AI agent sandboxing.",
    ),
    (
        "gemma4-dockerhub",
        "Google's Gemma 4 lightweight open-source AI models are now available on Docker Hub as OCI artifacts, enabling developers to pull and run them with familiar Docker commands and Docker Model Runner integration.",
        True,
        "Democratizes LLM deployment through standardized container workflows, directly relevant to InfoQ readers exploring AI/ML adoption and DevOps integration.",
    ),
    (
        "docker-offload-now-generally-available",
        "Docker Offload is now GA as a fully managed cloud service that moves the container engine to Docker's secure cloud infrastructure, enabling Docker Desktop use from VDI, managed desktops, and restricted networks with SOC 2 compliance.",
        True,
        "Addresses DevOps infrastructure barriers for enterprise teams, standardizes developer environments across constrained setups, and plans GPU/AI/ML workload support.",
    ),
    (
        "nodeweekly.com/issues/618",
        "Node Weekly issue 618 covers the Node.js 25.9 release, which introduces a --max-heap-size flag for memory control and improvements to iterable streams, alongside other ecosystem news.",
        True,
        "Relevant for InfoQ developers building Node.js server-side services who need to manage memory usage and leverage improved stream APIs.",
    ),
    (
        "aws-permission-delegation-now-generally-available-in-hcp-terraform",
        "HCP Terraform's AWS permission delegation feature reaches GA, allowing teams to delegate IAM permissions scoped per workspace without sharing admin credentials, enabling fine-grained least-privilege access management.",
        True,
        "Directly relevant for InfoQ DevOps practitioners managing infrastructure security and least-privilege access patterns in AWS environments.",
    ),
    (
        "hcp-terraform-adds-ip-allow-lists",
        "HCP Terraform now supports IP allow lists to restrict platform access from approved network addresses only, providing an additional security control for enterprise teams operating in regulated environments.",
        False,
        "",
    ),
    (
        "docker-model-runner-new-nvidia-dgx-station",
        "Docker Model Runner now supports NVIDIA's DGX Station (GB300) with 252 GB GPU memory and 7.1 TB/s bandwidth, enabling trillion-parameter model runs, multi-user GPU partitioning, and local agentic AI workflows via familiar Docker commands.",
        True,
        "Highly relevant to InfoQ's AI/ML and DevOps audience interested in large-scale local model inference and containerized AI infrastructure.",
    ),
    (
        "docker-sandboxes-run-agents-in-yolo-mode-safely",
        "Docker Sandboxes provides isolated microVM-based environments for AI coding agents (Claude Code, GitHub Copilot, etc.) to run autonomously with strong security boundaries, preventing host system access without restricting agent capabilities.",
        True,
        "Addresses critical security and architecture concerns for teams deploying AI agents in production, covering isolation patterns and platform-level enforcement.",
    ),
    (
        "building-a-news-roundup-with-docker-agent-docker-model-runner-and-skill",
        "Demonstrates building a local IT news roundup agent using Docker Agent, Docker Model Runner, and the Brave Search API—running a small language model (Qwen3.5-4B) entirely locally to retrieve, analyze, and summarize news without cloud AI costs.",
        True,
        "Showcases practical AI agent construction, local model inference, Docker containerization, and tool orchestration patterns highly relevant to InfoQ's software engineering and AI/ML audience.",
    ),
    (
        "modernizing-governance-on-hcp-with-multi-owner-and-global-automation",
        "Covers new HCP governance features including multi-owner project access and global automation policies that apply uniformly across all HCP resources, reducing manual governance overhead at scale.",
        False,
        "",
    ),
    (
        "lab3-accelerates-cloud-modernization-with-hashicorp-powered-unified-workflows",
        "Case study of how LAB3 used HashiCorp Terraform, Vault, and Consul to standardize cloud workflows across multiple client environments, significantly reducing provisioning time through unified infrastructure automation.",
        False,
        "",
    ),
    (
        "nodeweekly.com/issues/617",
        "Node Weekly issue 617 covers the impact of TypeScript 6.0 on Node.js developers, including changes to module resolution, new erasable type syntax, and other breaking changes that teams upgrading their stacks need to know.",
        True,
        "TypeScript 6.0 changes affect a large share of Node.js projects, making this directly relevant to InfoQ's software development and architecture audience.",
    ),
    (
        "trivy-supply-chain-compromise-what-docker-hub-users-should-know",
        "Documents a supply chain compromise of Aqua Security's Trivy vulnerability scanner (versions 0.69.4–0.69.6 and 'latest') that could exfiltrate CI/CD secrets, cloud credentials, and SSH keys from affected environments, with remediation steps and key lessons.",
        True,
        "A high-impact real-world supply chain attack with actionable lessons on digest pinning, mutable tag risks, and provenance verification—essential reading for InfoQ's DevOps and security audience.",
    ),
    (
        "agentic-runtime-security-solving-agentic-ai-identity-and-access-gaps",
        "Explains why traditional IAM systems fail for autonomous AI agents and proposes five imperatives—unique agent identities, eliminated standing privileges, intent-bound actions, runtime policy enforcement, and detailed audit trails—implemented via HashiCorp Vault.",
        True,
        "Covers critical architecture patterns for securing AI agents in enterprise systems, addressing identity/access control and least-privilege design essential for production AI implementations.",
    ),
    (
        "nodeweekly.com/issues/616",
        "Node Weekly issue 616 covers a community petition to prohibit AI-generated code contributions to Node.js core, sparking debate about code quality, maintainability, and AI's role in open source governance.",
        True,
        "The AI code authorship debate in open source directly affects engineering practices and governance, making it relevant to InfoQ's software craftsmanship and open source audience.",
    ),
    (
        "hcp-vault-dedicated-now-available-in-additional-aws-and-azure-regions",
        "HashiCorp has expanded HCP Vault Dedicated to new AWS regions (Stockholm, Paris) and Azure regions (Australia East, Australia Central), enabling improved latency, disaster recovery, and compliance with regional data residency requirements via cross-region replication.",
        True,
        "Relevant for software architects designing distributed systems and DevOps engineers implementing secrets management in multi-region cloud deployments.",
    ),
    (
        "adopting-hashicorp-vaults-transit-engine-high-performance-envelope-encryption-ariso-ai",
        "Ariso.ai implemented HashiCorp Vault's Transit Secrets Engine to achieve sub-millisecond (0.46ms median) envelope encryption for multi-tenant AI infrastructure, using context-based key derivation to provide cryptographic isolation at org, user, and session levels without managing thousands of individual keys.",
        True,
        "Production case study demonstrating encryption architecture, secrets management at scale, and multi-tenant data isolation patterns directly applicable to cloud-native and AI/ML platform development.",
    ),
    (
        "everything-as-code-for-your-security-lifecycle",
        "Advocates implementing 'everything as code' across infrastructure, applications, networking, and security using Terraform, Vault, Boundary, and Consul to automate security policies and reduce manual overhead for teams with unfavorable developer-to-security ratios.",
        True,
        "Directly addresses DevOps practitioners and platform engineers implementing infrastructure-as-code and security automation patterns aligned with modern cloud architecture practices.",
    ),
    (
        "building-day-2-ops-guardrails-with-terraform-and-packer",
        "Explains how Terraform and Packer implement five automated Day 2 operations guardrails—automatic cleanup, drift detection, continuous compliance validation, image revocation, and workspace visibility—to maintain secure, compliant, and cost-efficient infrastructure.",
        True,
        "Addresses critical platform engineering practices, infrastructure-as-code governance, and operational resilience strategies essential for modern DevOps and cloud architecture.",
    ),
    (
        "secure-remote-access-without-the-portal-tax-boundary-vs-other-vendors",
        "HashiCorp Boundary eliminates the 'portal tax' in secure remote access by using transparent sessions and native-tool workflows instead of web portals, integrating with Vault for passwordless credential injection and enabling SSH/RDP access through existing developer tools.",
        False,
        "",
    ),
    (
        "terraform-enterprise-12-upgrades-workflows-visibility-and-brownfield-migration",
        "Terraform Enterprise 1.2 introduces UI-driven resource discovery for importing unmanaged cloud infrastructure, makes the Explorer dashboard GA for centralized workspace visibility, and adds health check APIs alongside Day 2 operations capabilities.",
        True,
        "Directly addresses infrastructure-as-code practices, cloud operations automation, and DevOps workflows that InfoQ's architecture and engineering audience follows closely.",
    ),
    (
        "saving-banks-from-technical-debt-how-atruvia-built-secure-self-service-infrastructure",
        "Atruvia, a German banking IT provider, used Terraform and Vault to reduce cluster deployment time from 3 months to 2 hours and network setup from weeks to minutes, establishing a self-service infrastructure platform for its banking clients.",
        True,
        "Exemplifies infrastructure-as-code adoption, CI/CD automation, and organizational change management in a regulated industry—relevant to InfoQ's DevOps and cloud architecture readers.",
    ),
    (
        "how-benchling-saved-8000-hours-by-changing-how-it-used-terraform",
        "Benchling eliminated 8,000 developer hours annually by migrating from decentralized laptop-based Terraform execution to centralized HCP Terraform, improving workspace organization, security posture, and automation capabilities.",
        True,
        "Demonstrates concrete ROI from DevOps automation and infrastructure-as-code centralization, directly applicable to engineering teams evaluating or scaling Terraform adoption.",
    ),
    (
        "hcp-packer-adds-sbom-vulnerability-scanning",
        "HCP Packer now supports SBOM vulnerability scanning in public beta, scanning machine image components against MITRE's CVE database to identify vulnerabilities by severity and shift security detection earlier in the deployment pipeline.",
        True,
        "Addresses supply chain security and shift-left vulnerability detection—critical DevOps and engineering practices for cloud infrastructure teams building secure pipelines.",
    ),
    (
        "vault-radar-2025-recap-expanding-visibility-deepening-integration-simplifying-security",
        "HashiCorp Vault Radar expanded secrets detection throughout 2025 with integrations into VS Code, Jira, Slack, AWS S3, and Secrets Manager, plus webhook automation and AI-powered agentic workflows via MCP Server for discovering and remediating uncontrolled secrets.",
        True,
        "Covers DevSecOps automation, secrets sprawl management, and emerging AI integration patterns aligned with modern engineering security practices.",
    ),
    (
        "vault-certificates-secrets-inventory-reporting-visibility-audit-readiness",
        "HashiCorp has released beta features in HCP Vault Dedicated for certificates and secrets inventory reporting, providing lifecycle insights to identify risky long-lived credentials and export compliance data to ServiceNow and SIEM platforms.",
        False,
        "",
    ),
    (
        "securing-modern-workloads-with-hashicorp-vault-and-wif",
        "Explains how HashiCorp Vault combined with Workload Identity Federation eliminates static credentials by letting workloads authenticate with native cloud identities, which Vault exchanges for short-lived credentials—enforcing zero trust across multi-cloud, Kubernetes, and CI/CD environments.",
        True,
        "Addresses infrastructure security patterns, cloud-native architecture decisions, and secrets management practices directly relevant to InfoQ's DevOps and distributed systems audience.",
    ),
    (
        "how-world-bank-manages-hybrid-cloud-complexity-with-terraform",
        "Details how the World Bank uses Terraform to manage hybrid cloud infrastructure across on-premises and cloud environments at global scale, establishing governance guardrails and enabling consistent provisioning workflows.",
        True,
        "Large-scale hybrid cloud infrastructure management with IaC is a relevant engineering practices topic for InfoQ's cloud architecture and DevOps audience.",
    ),
    (
        "how-duke-energy-enforces-cloud-security-at-scale-with-terraform-vault-6-lessons",
        "Case study on how Duke Energy uses Terraform and Vault to enforce security policies and manage secrets across a large-scale regulated cloud environment, sharing six transferable lessons on compliance automation and least-privilege access.",
        True,
        "Six concrete lessons from cloud security at regulated enterprise scale make this relevant to InfoQ readers building compliant infrastructure and DevOps practices.",
    ),
]


def make_enrichment_html(summary: str, infoq_yes: bool, reason: str) -> str:
    esc_summary = he(summary)
    if infoq_yes:
        esc_reason = he(reason)
        badge = (
            '<span class="infoq-badge infoq-yes" title="Relevant for InfoQ.com">InfoQ Relevant ✓</span>'
            f' <span class="news-infoq-reason">{esc_reason}</span>'
        )
    else:
        badge = '<span class="infoq-badge infoq-no" title="Not typical InfoQ content">Not InfoQ</span>'
    return (
        "\n          <div class=\"news-enrichment\">\n"
        f'            <p class="news-summary"><span class="label">InfoQ relevance</span>{esc_summary}</p>\n'
        f'            <p class="news-infoq">{badge}</p>\n'
        "          </div>"
    )


def inject(html: str) -> str:
    def _replace_article(m: re.Match) -> str:
        body = m.group(1)
        # Already has enrichment – skip
        if "news-enrichment" in body:
            return m.group(0)
        # Find the article link to match a summary
        link_m = re.search(r'<a href="([^"]+)"', body)
        if not link_m:
            return m.group(0)
        link = link_m.group(1)
        for frag, summary, yes, reason in SUMMARIES:
            if frag in link:
                enrichment = make_enrichment_html(summary, yes, reason)
                return f"<article class=\"news-item\">{body}{enrichment}\n        </article>"
        return m.group(0)

    return re.sub(
        r'<article class="news-item">(.*?)</article>',
        _replace_article,
        html,
        flags=re.DOTALL,
    )


def main() -> None:
    html = OUTPUT_HTML.read_text(encoding="utf-8")
    new_html = inject(html)
    OUTPUT_HTML.write_text(new_html, encoding="utf-8")
    added = new_html.count("news-enrichment") - html.count("news-enrichment")
    print(f"Injected {added} enrichment blocks into {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
