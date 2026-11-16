import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "."

BarWidget {
  id: root
  moduleName: "kel.github-reports"
  property bool popupOpen: false
  readonly property bool opened: popupOpen
  property string filter: "all"
  readonly property var reportData: Reports.data
  readonly property var filtered: reportData.items.filter(function(row) {
    return (root.filter === "all" || (root.filter === "unread" ? row.unread : row.kind === root.filter))
      && (search.text === "" || (row.title + " " + row.repository).toLowerCase().indexOf(search.text.toLowerCase()) !== -1)
  })

  function close() { popupOpen = false }
  function open() { popupOpen = true }
  function toggle() { popupOpen = !popupOpen }
  function refresh() { Reports.run(["refresh"]) }
  function status() {
    return JSON.stringify({ loaded: Reports.loaded, busy: Reports.busy, error: Reports.error,
      owner: reportData.owner, total: reportData.total, unread: reportData.unread,
      automatic: reportData.automatic, checked: reportData.checked })
  }
  function browse(url) {
    var launched = Qt.openUrlExternally(url)
    if (!launched) Reports.error = strings.t("browserError")
    return launched
  }
  function count(kind) {
    return reportData.items.filter(function(row) { return row.kind === kind }).length
  }

  Component.onCompleted: Reports.start()
  implicitWidth: button.implicitWidth
  implicitHeight: barSize

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  ShellIpc {
    target: "kel.github-reports"
    function open() { root.open() }
    function close() { root.close() }
    function toggle() { root.toggle() }
    function refresh() { root.refresh() }
    function status(): string { return root.status() }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\uf09b"
    active: root.reportData.unread > 0 || Reports.error !== ""
    tooltipText: Reports.error !== "" ? strings.t("tooltip.error")
      : strings.tn("tooltip.reports", root.reportData.total).arg(Commons.I18n.formatNumber(root.reportData.total))
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton) root.browse(root.reportData.url)
      else if (mouseButton === Qt.MiddleButton) root.refresh()
      else root.toggle()
    }

    Rectangle {
      visible: root.reportData.unread > 0 || Reports.error !== ""
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.topMargin: 1
      implicitWidth: Math.max(Style.space(13), badge.implicitWidth + Style.space(4))
      height: Style.space(13)
      radius: height / 2
      color: Commons.Color.urgent
      Text {
        id: badge
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: Reports.error !== "" ? "!" : root.reportData.unread > 99 ? "99+" : Commons.I18n.formatNumber(root.reportData.unread)
        color: Commons.Color.background
        font.family: Style.font.family
        font.pixelSize: Style.space(9)
        font.bold: true
      }
    }
  }

  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(Style.space(560))
    contentHeight: popup.fittedContentHeight(content.implicitHeight)

    ColumnLayout {
      id: content
      width: parent.width
      spacing: Style.space(10)

      RowLayout {
        Layout.fillWidth: true
        PlainText {
          Layout.fillWidth: true
          text: strings.t("title")
          font.pixelSize: Style.font.subtitle
          font.bold: true
        }
        Controls.Button {
          text: Reports.busy ? strings.t("refreshing") : strings.t("refresh")
          enabled: !Reports.busy
          onClicked: root.refresh()
        }
      }
      PlainText {
        Layout.fillWidth: true
        text: root.reportData.owner ? strings.t("scope").arg(root.reportData.owner) : strings.t("connecting")
        wrapMode: Text.Wrap
        opacity: 0.7
      }
      PlainText {
        id: accountNotice
        Layout.fillWidth: true
        text: strings.t("account.notice")
        wrapMode: Text.Wrap
        font.pixelSize: Style.font.bodySmall
        opacity: 0.8
      }
      PlainText {
        id: accountSetup
        Layout.fillWidth: true
        visible: root.reportData.owner === "" || Reports.error !== ""
        text: strings.t("account.setup")
        wrapMode: Text.Wrap
        font.pixelSize: Style.font.bodySmall
      }
      PlainText {
        Layout.fillWidth: true
        text: strings.t("summary")
          .arg(Commons.I18n.formatNumber(root.reportData.total))
          .arg(Commons.I18n.formatNumber(root.count("bug")))
          .arg(Commons.I18n.formatNumber(root.count("feature")))
          .arg(Commons.I18n.formatNumber(root.count("other")))
        wrapMode: Text.Wrap
      }
      PlainText {
        Layout.fillWidth: true
        visible: Reports.error !== ""
        text: Reports.error
        wrapMode: Text.Wrap
        color: Commons.Color.urgent
      }
      PlainText {
        Layout.fillWidth: true
        visible: root.reportData.truncated
        text: strings.t("truncated")
        wrapMode: Text.Wrap
      }
      RowLayout {
        Layout.fillWidth: true
        Controls.ComboBox {
          Layout.preferredWidth: Style.space(160)
          model: [strings.t("filter.all"), strings.t("filter.unread"), strings.t("filter.bug"),
            strings.t("filter.feature"), strings.t("filter.other")]
          onActivated: root.filter = ["all", "unread", "bug", "feature", "other"][currentIndex]
        }
        Controls.TextField {
          id: search
          Layout.fillWidth: true
          placeholderText: strings.t("search")
        }
      }
      Controls.ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: root.filtered.length === 0 ? Style.space(80)
          : Math.min(Style.space(340), Math.max(Style.space(70), popup.availableCardHeight
            - Style.space(410) - accountNotice.implicitHeight - (accountSetup.visible ? accountSetup.implicitHeight + content.spacing : 0)))
        clip: true
        contentWidth: availableWidth
        ListView {
          id: list
          model: root.filtered
          spacing: Style.space(4)
          delegate: Rectangle {
            id: row
            required property var modelData
            width: list.width
            height: Style.space(72)
            radius: Style.cornerRadius
            color: mouse.containsMouse || readButton.hovered
              ? Style.hoverFillFor(Commons.Color.popups.text, Commons.Color.accent) : "transparent"
            RowLayout {
              anchors.fill: parent
              anchors.margins: Style.space(6)
              anchors.rightMargin: readControls.width + Style.space(14)
              spacing: Style.space(8)
              Rectangle {
                Layout.preferredWidth: Style.space(6)
                Layout.preferredHeight: Style.space(6)
                radius: width / 2
                color: row.modelData.unread ? Commons.Color.accent : "transparent"
              }
              ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.space(3)
                PlainText {
                  Layout.fillWidth: true
                  text: row.modelData.title
                  font.bold: row.modelData.unread
                  elide: Text.ElideRight
                }
                PlainText {
                  Layout.fillWidth: true
                  text: strings.t("report.meta").arg(row.modelData.repository)
                    .arg(Commons.I18n.formatNumber(row.modelData.number))
                    .arg(strings.t("filter." + row.modelData.kind))
                  font.pixelSize: Style.font.bodySmall
                  opacity: 0.7
                  elide: Text.ElideRight
                }
                PlainText {
                  Layout.fillWidth: true
                  text: new Date(row.modelData.updated).toLocaleString(Qt.locale(Commons.I18n.formatLocale), Locale.ShortFormat)
                  font.pixelSize: Style.font.bodySmall
                  opacity: 0.6
                  elide: Text.ElideRight
                }
              }
            }
            MouseArea {
              id: mouse
              anchors.fill: parent
              anchors.rightMargin: readControls.width + Style.space(12)
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: {
                if (root.browse(row.modelData.url)) Reports.run(["read", row.modelData.id])
              }
            }
            Column {
              id: readControls
              width: readButton.implicitWidth
              anchors.right: parent.right
              anchors.rightMargin: Style.space(6)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(3)
              PlainText {
                objectName: "readStatusLabel"
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: row.modelData.unread ? strings.t("status.unread") : strings.t("status.read")
                color: row.modelData.unread ? Commons.Color.accent : Commons.Color.popups.text
                opacity: row.modelData.unread ? 1 : 0.65
                font.bold: row.modelData.unread
                font.pixelSize: Style.font.bodySmall
              }
              Controls.Button {
                id: readButton
                objectName: "readStatusButton"
                width: parent.width
                text: row.modelData.unread ? strings.t("markRead") : strings.t("markUnread")
                enabled: !Reports.busy
                onClicked: Reports.run([row.modelData.unread ? "read" : "unread", row.modelData.id])
              }
            }
          }
          PlainText {
            anchors.centerIn: parent
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            visible: root.filtered.length === 0
            text: !Reports.loaded || !root.reportData.checked ? strings.t("waiting")
              : root.reportData.items.length === 0 ? strings.t("empty") : strings.t("noMatch")
            wrapMode: Text.Wrap
          }
        }
      }
      RowLayout {
        Layout.fillWidth: true
        Controls.Button {
          Layout.fillWidth: true
          text: strings.t("openGitHub")
          onClicked: root.browse(root.reportData.url)
        }
        Controls.Button {
          text: strings.t("reviewed")
          enabled: root.reportData.unread > 0 && !Reports.busy
          onClicked: Reports.run(["read", "all"])
        }
      }
      Controls.CheckBox {
        text: strings.t("automatic")
        checked: root.reportData.automatic
        enabled: Reports.loaded && !Reports.busy
        onClicked: Reports.run(["automatic", checked ? "on" : "off"])
      }
      PlainText {
        Layout.fillWidth: true
        text: root.reportData.checked ? strings.t("checked").arg(
          new Date(root.reportData.checked).toLocaleString(Qt.locale(Commons.I18n.formatLocale), Locale.ShortFormat))
          : strings.t("notChecked")
        font.pixelSize: Style.font.bodySmall
        opacity: 0.6
        wrapMode: Text.Wrap
      }
    }
  }
}
