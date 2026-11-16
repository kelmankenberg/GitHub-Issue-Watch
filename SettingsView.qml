import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons
import qs.Commons as Commons
import "."

Controls.ScrollView {
  id: root
  property real maximumHeight: Style.space(700)
  property bool accountHelpOpen: Reports.data.owner === ""
  signal browseRequested(string url)
  readonly property var intervals: Reports.data.refreshOptions
  readonly property var scheduleLabels: intervals.map(function(minutes) {
    if (minutes === 0) return strings.t("schedule.manual")
    if (minutes >= 60) return strings.tn("schedule.hours", minutes / 60)
      .arg(Commons.I18n.formatNumber(minutes / 60))
    return strings.tn("schedule.minutes", minutes).arg(Commons.I18n.formatNumber(minutes))
  })

  implicitHeight: Math.min(settingsContent.implicitHeight, Math.max(Style.space(100), maximumHeight))
  contentWidth: availableWidth
  clip: true

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  ColumnLayout {
    id: settingsContent
    width: root.availableWidth
    spacing: Style.space(8)

    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)
      PlainText {
        Layout.fillWidth: true
        text: strings.t("settings.refresh")
        font.bold: true
      }
      Controls.ComboBox {
        objectName: "refreshSchedule"
        Layout.preferredWidth: Style.space(200)
        model: root.scheduleLabels
        currentIndex: root.intervals.indexOf(Reports.data.automatic ? Reports.data.refreshMinutes : 0)
        enabled: Reports.loaded && !Reports.busy
        onActivated: function(index) { Reports.run(["schedule", String(root.intervals[index])]) }
      }
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("settings.scheduleHint")
      wrapMode: Text.Wrap
      opacity: 0.7
      font.pixelSize: Style.font.bodySmall
    }
    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)
      Controls.CheckBox {
        objectName: "badgePreference"
        Layout.fillWidth: true
        text: strings.t("settings.badge")
        checked: Reports.data.badgeEnabled
        enabled: Reports.loaded && !Reports.busy
        Accessible.description: strings.t("settings.badgeHelp")
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: strings.t("settings.badgeHelp")
        onClicked: Reports.run(["badge", checked ? "on" : "off"])
      }
      Controls.CheckBox {
        objectName: "desktopPreference"
        Layout.fillWidth: true
        text: strings.t("settings.desktop")
        checked: Reports.data.desktopNotifications
        enabled: Reports.loaded && !Reports.busy
        Accessible.description: strings.t("settings.notificationHelp")
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: strings.t("settings.notificationHelp")
        onClicked: Reports.run(["notifications", checked ? "on" : "off"])
      }
    }
    Rectangle {
      Layout.fillWidth: true
      Layout.topMargin: Style.space(4)
      Layout.bottomMargin: Style.space(4)
      implicitHeight: 1
      color: Commons.Color.popups.border
      opacity: 0.5
    }
    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)
      PlainText {
        Layout.fillWidth: true
        text: Reports.data.owner ? strings.t("settings.account").arg(Reports.data.owner) : strings.t("connecting")
        wrapMode: Text.Wrap
        font.bold: true
      }
      Controls.Button {
        objectName: "accountHelpButton"
        text: strings.t(root.accountHelpOpen ? "settings.hideHelp" : "settings.signInHelp")
        onClicked: root.accountHelpOpen = !root.accountHelpOpen
      }
    }
    PlainText {
      Layout.fillWidth: true
      text: strings.t("settings.accountHint")
      wrapMode: Text.Wrap
      font.pixelSize: Style.font.bodySmall
      opacity: 0.7
    }
    PlainText {
      objectName: "accountHelp"
      Layout.fillWidth: true
      visible: root.accountHelpOpen
      text: strings.t("account.setup")
      wrapMode: Text.Wrap
      font.pixelSize: Style.font.bodySmall
      opacity: 0.7
    }
    Rectangle {
      Layout.fillWidth: true
      Layout.topMargin: Style.space(4)
      Layout.bottomMargin: Style.space(4)
      implicitHeight: 1
      color: Commons.Color.popups.border
      opacity: 0.5
    }
    RowLayout {
      Layout.fillWidth: true
      PlainText {
        Layout.fillWidth: true
        text: strings.t("settings.help")
        font.bold: true
      }
      PlainText {
        text: strings.t("settings.version").arg(Reports.data.pluginVersion)
        opacity: 0.7
        font.pixelSize: Style.font.bodySmall
      }
    }
    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)
      Controls.Button {
        objectName: "reportPluginBug"
        Layout.fillWidth: true
        text: strings.t("feedback.bug")
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: strings.t("settings.feedbackHint")
        onClicked: root.browseRequested("https://github.com/kelmankenberg/OmaRepoReport/issues/new?template=bug_report.yml")
      }
      Controls.Button {
        objectName: "requestPluginFeature"
        Layout.fillWidth: true
        text: strings.t("feedback.feature")
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: strings.t("settings.feedbackHint")
        onClicked: root.browseRequested("https://github.com/kelmankenberg/OmaRepoReport/issues/new?template=feature_request.yml")
      }
      Controls.Button {
        objectName: "pluginRepository"
        Layout.fillWidth: true
        text: strings.t("settings.repository")
        onClicked: root.browseRequested("https://github.com/kelmankenberg/OmaRepoReport")
      }
    }
  }
}
