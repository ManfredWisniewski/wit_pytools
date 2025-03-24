import subprocess


#def ncdelfile(subdir, file, dryrun):
#    if dryrun:
#        print(' -  del: ' + file)
#    else:
#        os.remove((os.path.join(subdir, file)))

def ncmovefile(subdir, file, destdir, nfile, dryrun):
    if dryrun:
        print(' - move: ' + os.path.join(subdir, file))
        print('     to: ' + destdir + "\\" + nfile)
    else:
        try:
            subprocess.run(["php", "occ", "files:move", subdir + '/' + file, destdir+ '/' + file], check=True)
        except:
            #ignore directory already exists error TODO: make more elegant
            True

# def nccopyfile(subdir, file, destdir, nfile, dryrun):
#     if dryrun:
#         print(' - copy: ' + os.path.join(subdir, file))
#         print('     to: ' + destdir + "\\" + nfile)
#     else:
#         try:
#             #os.rename((os.path.join(subdir, file)), (destdir + "/" + nfile))
#             shutil.copy(os.path.join(subdir, file), destdir + "/" + nfile)
#         except:
#             #ignore directory already exists error TODO: make more elegant
#             True

# def ncmoveallfiles(sourcedir, destdir, dryrun):
#     if os.path.isdir(sourcedir):
#         if dryrun:
#             files = os.listdir(sourcedir)
#             for file in files:
#                 print(' - move: ' + os.path.join(sourcedir, file))
#                 print('     to: ' + destdir + "\\" + file)
#         else:
#             files = os.listdir(sourcedir)
#             for file in files:
#                 try:
#                     print(' - moving: ' + os.path.join(sourcedir, file))
#                     print('       to: ' + destdir + "\\" + file)
#                     shutil.move(os.path.join(sourcedir, file), destdir)
#                 except:
#                     #ignore directory already exists error TODO: make more elegant
#                     True
#     else:
#         print('Source not found - skipped: ' + sourcedir)
