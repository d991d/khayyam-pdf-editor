import SwiftUI

struct WelcomeView: View {
    @EnvironmentObject var viewModel: PDFEditorViewModel

    var body: some View {
        VStack(spacing: 28) {
            // App icon + name
            VStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 22)
                        .fill(Color.accentColor)
                        .frame(width: 88, height: 88)
                        .shadow(color: Color.accentColor.opacity(0.35), radius: 14, y: 6)
                    Image(systemName: "doc.richtext.fill")
                        .font(.system(size: 44))
                        .foregroundColor(.white)
                }

                Text("Khayyam PDF Editor")
                    .font(.system(size: 26, weight: .bold, design: .serif))

                Text("by d991d")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 6) {
                Text("Open, annotate, merge, and edit PDF documents")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            // Quick actions
            VStack(spacing: 12) {
                WelcomeAction(
                    icon: "folder.badge.plus",
                    title: "Open PDF",
                    subtitle: "Open an existing PDF file",
                    action: viewModel.openPDF
                )

                WelcomeAction(
                    icon: "arrow.triangle.merge",
                    title: "Merge PDFs",
                    subtitle: "Combine multiple PDFs into one",
                    action: { viewModel.showMergeSheet = true }
                )
            }
            .frame(maxWidth: 400)

            // Drag & drop hint
            Text("or drag & drop a PDF file here")
                .font(.caption)
                .foregroundStyle(.tertiary)

            // Footer — website + help
            HStack(spacing: 16) {
                Link("d991d.com", destination: URL(string: "https://www.d991d.com")!)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
        .onDrop(of: [.pdf, .fileURL], isTargeted: nil) { providers in
            for provider in providers {
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url, url.pathExtension.lowercased() == "pdf" else { return }
                    Task { @MainActor in
                        viewModel.loadPDF(from: url)
                    }
                }
            }
            return true
        }
    }
}

struct WelcomeAction: View {
    let icon: String
    let title: String
    let subtitle: String
    let action: () -> Void

    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(Color.accentColor)
                    .frame(width: 32)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.headline)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .foregroundStyle(.tertiary)
            }
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isHovered ? Color(nsColor: .controlBackgroundColor) : Color(nsColor: .windowBackgroundColor))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}
