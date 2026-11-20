#define AppName "ATMO ESFERA FX"
[Setup]
AppId={{C0CF3D27-70B9-4F88-B176-1C54762139B1}
AppName={#AppName}
AppVersion=2026.11.20
AppPublisher=Espais Geodèsics
DefaultDirName={localappdata}\Programs\ATMO ESFERA FX
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=ATMO_ESFERA_FX_Instal_lador_Windows
SetupIconFile=..\build\clean\atmo_assets\atmo.ico
UninstallDisplayIcon={app}\ATMO_ESFERA_FX.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
[Languages]
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"
[Files]
Source: "..\dist\ATMO_ESFERA_FX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LLEGEIX_ME.txt"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ATMO_ESFERA_FX.exe"; WorkingDir: "{app}"; IconFilename: "{app}\ATMO_ESFERA_FX.exe"; AppUserModelID: "ATMO.ESFERA.FX"
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\ATMO_ESFERA_FX.exe"; WorkingDir: "{app}"; IconFilename: "{app}\ATMO_ESFERA_FX.exe"; AppUserModelID: "ATMO.ESFERA.FX"
[Run]
Filename: "{app}\ATMO_ESFERA_FX.exe"; Description: "Obrir ATMO ESFERA FX"; Flags: nowait postinstall skipifsilent
[Code]
var PreviousFolder: TInputDirWizardPage;
procedure InitializeWizard;
begin
  PreviousFolder := CreateInputDirPage(wpSelectDir, 'Conservar els projectes anteriors',
    'Opcional: tria la carpeta on utilitzaves ATMO fins ara.',
    'Es copiaran PROJECTES i GRAVACIONS, inclosa la distribucio de finestres. No se sobreescriuran fitxers existents. Deixa-ho buit si no vols copiar res.', False, '');
  PreviousFolder.Add('Carpeta anterior d''ATMO (opcional):');
end;
procedure CopyMissing(const Source, Destination: String);
var Entry: TFindRec; FromPath, ToPath: String;
begin
  if not DirExists(Source) then Exit;
  ForceDirectories(Destination);
  if FindFirst(AddBackslash(Source) + '*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then begin
          FromPath := AddBackslash(Source) + Entry.Name;
          ToPath := AddBackslash(Destination) + Entry.Name;
          if (Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            CopyMissing(FromPath, ToPath)
          else if not FileExists(ToPath) then
            if not FileCopy(FromPath, ToPath, True) then
              Log('No s''ha pogut copiar: ' + FromPath);
        end;
      until not FindNext(Entry);
    finally FindClose(Entry); end;
  end;
end;
procedure CurStepChanged(CurStep: TSetupStep);
var Folder, Target: String;
begin
  if CurStep = ssPostInstall then begin
    Folder := Trim(PreviousFolder.Values[0]);
    if Folder <> '' then begin
      Target := ExpandConstant('{localappdata}\ATMO ESFERA FX');
      if CompareText(RemoveBackslashUnlessRoot(Folder), RemoveBackslashUnlessRoot(Target)) <> 0 then begin
        CopyMissing(AddBackslash(Folder) + 'PROJECTES', AddBackslash(Target) + 'PROJECTES');
        CopyMissing(AddBackslash(Folder) + 'GRAVACIONS', AddBackslash(Target) + 'GRAVACIONS');
      end;
    end;
  end;
end;
